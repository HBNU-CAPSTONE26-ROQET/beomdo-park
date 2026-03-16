from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from .config import ARTIFACTS_DIR, DATA_DIR, MODEL_DIR, REPORT_DIR, DatasetConfig, ExportConfig, ModelConfig, TrainingConfig
from .dataset import QECPathDataset, generate_synthetic_dataset, _build_surface_code_circuit, _detector_index_map, CANONICAL_COORDS, DATA_QUBIT_COORDS
from .model import PolicyMLP, logits_to_mask
from .utils import ensure_dirs, set_seed, write_json


def split_indices(num_samples: int, config: TrainingConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = np.arange(num_samples)
    np.random.shuffle(indices)
    train_end = int(num_samples * config.train_ratio)
    val_end = train_end + int(num_samples * config.val_ratio)
    return indices[:train_end], indices[train_end:val_end], indices[val_end:]


def predictions_from_logits(logits: torch.Tensor, thresholds: np.ndarray | None = None) -> np.ndarray:
    if thresholds is None:
        return logits_to_mask(logits).cpu().numpy().astype(np.int8)
    threshold_tensor = torch.tensor(thresholds, dtype=logits.dtype, device=logits.device)
    probabilities = torch.sigmoid(logits)
    return (probabilities >= threshold_tensor).cpu().numpy().astype(np.int8)


def _metrics_from_predictions(predictions: np.ndarray, labels: np.ndarray) -> dict[str, float | list[float]]:
    exact_match = float(np.mean(np.all(predictions == labels, axis=1)))
    bit_acc = float(np.mean(predictions == labels))
    pred_hamming = predictions.sum(axis=1)
    true_hamming = labels.sum(axis=1)
    return {
        "exact_match": exact_match,
        "bit_acc": bit_acc,
        "pred_mean_hamming": float(np.mean(pred_hamming)),
        "true_mean_hamming": float(np.mean(true_hamming)),
        "pred_zero_mask_ratio": float(np.mean(pred_hamming == 0)),
        "true_zero_mask_ratio": float(np.mean(true_hamming == 0)),
        "bit_activation_rate": [float(value) for value in np.mean(predictions, axis=0)],
    }


def evaluate(
    model: PolicyMLP,
    loader: DataLoader,
    device: torch.device,
    thresholds: np.ndarray | None = None,
) -> dict[str, float | list[float]]:
    criterion = nn.BCEWithLogitsLoss()
    total_loss = 0.0
    count = 0
    prediction_batches: list[np.ndarray] = []
    label_batches: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)
            logits = model(features)
            loss = criterion(logits, labels)
            total_loss += float(loss.item()) * features.size(0)
            predictions = predictions_from_logits(logits, thresholds)
            label_array = labels.cpu().numpy().astype(np.int8)
            prediction_batches.append(predictions)
            label_batches.append(label_array)
            count += int(labels.size(0))

    if count == 0:
        return {
            "loss": 0.0,
            "exact_match": 0.0,
            "bit_acc": 0.0,
            "pred_mean_hamming": 0.0,
            "true_mean_hamming": 0.0,
            "pred_zero_mask_ratio": 0.0,
            "true_zero_mask_ratio": 0.0,
            "bit_activation_rate": [],
        }

    predictions = np.concatenate(prediction_batches, axis=0)
    label_array = np.concatenate(label_batches, axis=0)
    metrics = _metrics_from_predictions(predictions, label_array)
    metrics["loss"] = total_loss / count
    return metrics


def evaluate_subset(
    model: PolicyMLP,
    features: np.ndarray,
    labels: np.ndarray,
    device: torch.device,
    thresholds: np.ndarray | None = None,
) -> dict[str, float | list[float]]:
    if len(labels) == 0:
        return {
            "sample_count": 0,
            "exact_match": 0.0,
            "bit_acc": 0.0,
            "pred_mean_hamming": 0.0,
            "true_mean_hamming": 0.0,
            "pred_zero_mask_ratio": 0.0,
            "true_zero_mask_ratio": 0.0,
            "bit_activation_rate": [],
        }

    model.eval()
    with torch.no_grad():
        feature_tensor = torch.tensor(features, dtype=torch.float32, device=device)
        logits = model(feature_tensor)
        predictions = predictions_from_logits(logits, thresholds)
    metrics = _metrics_from_predictions(predictions, labels.astype(np.int8))
    metrics["sample_count"] = int(len(labels))
    return metrics


def compute_pos_weight(labels: np.ndarray) -> np.ndarray:
    positives = labels.sum(axis=0).astype(np.float32)
    negatives = labels.shape[0] - positives
    pos_weight = np.ones_like(positives, dtype=np.float32)
    valid = positives > 0
    pos_weight[valid] = negatives[valid] / positives[valid]
    return np.clip(pos_weight, 1.0, 4.0)


def optimize_thresholds(
    model: PolicyMLP,
    features: np.ndarray,
    labels: np.ndarray,
    device: torch.device,
) -> np.ndarray:
    if len(labels) == 0:
        return np.full((0,), 0.5, dtype=np.float32)

    with torch.no_grad():
        feature_tensor = torch.tensor(features, dtype=torch.float32, device=device)
        probabilities = torch.sigmoid(model(feature_tensor)).cpu().numpy()

    thresholds = np.full(labels.shape[1], 0.5, dtype=np.float32)
    threshold_grid = np.linspace(0.1, 0.9, 17, dtype=np.float32)

    for bit_index in range(labels.shape[1]):
        target = labels[:, bit_index].astype(np.int8)
        if int(target.sum()) == 0:
            thresholds[bit_index] = 1.0
            continue

        best_threshold = 0.5
        best_score = -1.0
        best_rate_gap = float("inf")
        target_rate = float(np.mean(target))
        for threshold in threshold_grid:
            prediction = (probabilities[:, bit_index] >= threshold).astype(np.int8)
            bit_acc = float(np.mean(prediction == target))
            rate_gap = abs(float(np.mean(prediction)) - target_rate)
            if bit_acc > best_score or (bit_acc == best_score and rate_gap < best_rate_gap) or (
                bit_acc == best_score and rate_gap == best_rate_gap and threshold > best_threshold
            ):
                best_score = bit_acc
                best_rate_gap = rate_gap
                best_threshold = float(threshold)
        thresholds[bit_index] = best_threshold

    return thresholds


def quantized_validation(
    model: PolicyMLP,
    features: np.ndarray,
    labels: np.ndarray,
    thresholds: np.ndarray,
    device: torch.device,
) -> dict:
    """Quantize weights to INT8/INT16, dequantize, measure accuracy drop vs float32."""
    export_config = ExportConfig()
    state = model.state_dict()
    q_state = {}
    for name, param in state.items():
        limit = export_config.scale_weight if "weight" in name else export_config.scale_bias
        array = param.detach().cpu().numpy()
        max_abs = float(np.max(np.abs(array)))
        if max_abs == 0:
            q_state[name] = param.clone()
            continue
        scale = limit / max_abs
        quantized = np.clip(np.round(array * scale), -limit, limit)
        q_state[name] = torch.tensor(quantized / scale, dtype=param.dtype)

    q_model = PolicyMLP(ModelConfig(
        input_dim=int(state["layers.0.weight"].shape[1]),
        hidden_dim=int(state["layers.0.weight"].shape[0]),
        output_dim=int(state["layers.2.weight"].shape[0]),
    ))
    q_model.load_state_dict(q_state)
    q_model.to(device)
    return evaluate_subset(q_model, features, labels, device, thresholds)


def _find_logical_support(task: str, error_type: str) -> list[int]:
    """Find which data-qubit indices (0-8) flip the observable when a single error is injected.

    For rotated_memory_z + X error → Z logical support.
    For rotated_memory_x + Z error → X logical support.
    """
    import stim

    config = DatasetConfig(num_samples=1)
    circuit = _build_surface_code_circuit(task, config)

    noise_gates = {"DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR",
                   "PAULI_CHANNEL_1", "PAULI_CHANNEL_2"}
    c_clean = stim.Circuit()
    for inst in circuit.flattened():
        if inst.name not in noise_gates:
            c_clean.append(inst)

    coords = circuit.get_final_qubit_coordinates()
    data_to_circuit: dict[int, int] = {}
    for ci, coord in coords.items():
        for di, dc in enumerate(DATA_QUBIT_COORDS):
            if abs(coord[0] - dc[0]) < 0.1 and abs(coord[1] - dc[1]) < 0.1:
                data_to_circuit[di] = ci
                break

    sampler = c_clean.compile_detector_sampler(seed=0)
    _, obs_base = sampler.sample(1, separate_observables=True)
    base_val = int(obs_base[0, 0])

    error_gate = f"{error_type}_ERROR"
    support: list[int] = []

    for di in range(9):
        if di not in data_to_circuit:
            continue
        ci = data_to_circuit[di]
        c_err = stim.Circuit()
        inserted = False
        for inst in c_clean.flattened():
            c_err.append(inst)
            if not inserted and inst.name == "TICK":
                inserted = True
                c_err.append(stim.CircuitInstruction(error_gate, [ci], [1.0]))
        s_err = c_err.compile_detector_sampler(seed=0)
        _, obs_err = s_err.sample(1, separate_observables=True)
        if int(obs_err[0, 0]) != base_val:
            support.append(di)

    return support


def measure_logical_error_rate(
    model_x: PolicyMLP,
    model_z: PolicyMLP,
    thresholds_x: np.ndarray,
    thresholds_z: np.ndarray,
    device: torch.device,
    num_shots: int = 10000,
    seed: int = 42,
) -> dict:
    """Run Stim simulation with model-predicted masks and measure logical failure rate."""
    import stim
    from pymatching import Matching

    config = DatasetConfig(num_samples=num_shots)

    z_logical_support = _find_logical_support("surface_code:rotated_memory_z", "X")
    x_logical_support = _find_logical_support("surface_code:rotated_memory_x", "Z")

    results = {}

    for task, path_label, model_path, thresholds_path, logical_support in [
        ("surface_code:rotated_memory_z", "x", model_x, thresholds_x, z_logical_support),
        ("surface_code:rotated_memory_x", "z", model_z, thresholds_z, x_logical_support),
    ]:
        circuit = _build_surface_code_circuit(task, config)
        detector_indices = _detector_index_map(circuit, config.rounds)
        sampler = circuit.compile_detector_sampler(seed=seed + hash(path_label) % 1000)
        matching = Matching.from_detector_error_model(circuit.detector_error_model(decompose_errors=True))

        detector_events, logical_observables = sampler.sample(shots=num_shots, separate_observables=True)
        observables = logical_observables.reshape(-1).astype(np.int8)
        features = detector_events[:, detector_indices].astype(np.float32)

        # Baseline: PyMatching decoder
        baseline_result = matching.decode_batch(detector_events)
        baseline_predictions = (baseline_result[0] if isinstance(baseline_result, tuple) else baseline_result).reshape(-1).astype(np.int8)
        baseline_errors = int(np.sum(baseline_predictions != observables))

        # Model prediction
        the_model = model_path
        the_model.eval()
        with torch.no_grad():
            feature_tensor = torch.tensor(features, dtype=torch.float32, device=device)
            logits = the_model(feature_tensor)
            prob = torch.sigmoid(logits).cpu().numpy()
        threshold_vec = np.array(thresholds_path, dtype=np.float32)
        predicted_masks = (prob >= threshold_vec).astype(np.int8)

        support_arr = np.array(logical_support)
        model_logical = predicted_masks[:, support_arr].sum(axis=1) % 2
        model_errors = int(np.sum(model_logical.astype(np.int8) != observables))

        results[f"{path_label}_path"] = {
            "num_shots": num_shots,
            "logical_support_indices": logical_support,
            "baseline_logical_errors": baseline_errors,
            "baseline_logical_error_rate": float(baseline_errors / num_shots),
            "model_logical_errors": model_errors,
            "model_logical_error_rate": float(model_errors / num_shots),
        }

    return results


def summarize_dataset(dataset: dict[str, np.ndarray]) -> dict[str, object]:
    x_hamming = dataset["x_masks"].sum(axis=1).astype(int)
    z_hamming = dataset["z_masks"].sum(axis=1).astype(int)
    return {
        "num_samples": int(dataset["x_features"].shape[0]),
        "ambiguity_rate": float(np.mean(dataset["ambiguity"])),
        "trusted_sampling": dict(dataset["meta"][0]),
        "x_feature_activation": [float(value) for value in dataset["x_features"].mean(axis=0)],
        "z_feature_activation": [float(value) for value in dataset["z_features"].mean(axis=0)],
        "x_mask_activation": [float(value) for value in dataset["x_masks"].mean(axis=0)],
        "z_mask_activation": [float(value) for value in dataset["z_masks"].mean(axis=0)],
        "x_vote_usage": [float(value) for value in dataset["x_vote_usage"]],
        "z_vote_usage": [float(value) for value in dataset["z_vote_usage"]],
        "x_dead_mask_bits": [int(index) for index, value in enumerate(dataset["x_masks"].mean(axis=0)) if value == 0.0],
        "z_dead_mask_bits": [int(index) for index, value in enumerate(dataset["z_masks"].mean(axis=0)) if value == 0.0],
        "x_dead_vote_bits": [int(index) for index, value in enumerate(dataset["x_vote_usage"]) if value == 0.0],
        "z_dead_vote_bits": [int(index) for index, value in enumerate(dataset["z_vote_usage"]) if value == 0.0],
        "x_hamming_distribution": {str(key): int(value) for key, value in sorted(Counter(x_hamming.tolist()).items())},
        "z_hamming_distribution": {str(key): int(value) for key, value in sorted(Counter(z_hamming.tolist()).items())},
        "mapping_trace": dict(dataset["meta"][0]).get("mapping_trace", {}),
    }


def train_one_path(
    path_name: str,
    features: np.ndarray,
    labels: np.ndarray,
    ambiguity: np.ndarray,
    model_config: ModelConfig,
    training_config: TrainingConfig,
    device: torch.device,
    artifact_prefix: str = "",
) -> dict:
    train_idx, val_idx, test_idx = split_indices(len(labels), training_config)
    datasets = {
        "train": QECPathDataset(features[train_idx], labels[train_idx]),
        "val": QECPathDataset(features[val_idx], labels[val_idx]),
        "test": QECPathDataset(features[test_idx], labels[test_idx]),
    }
    loaders = {
        split: DataLoader(dataset, batch_size=training_config.batch_size, shuffle=(split == "train"))
        for split, dataset in datasets.items()
    }

    model = PolicyMLP(model_config).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=training_config.learning_rate)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=training_config.num_epochs, eta_min=1e-5)
    pos_weight = compute_pos_weight(labels[train_idx])
    pos_weight_tensor = torch.tensor(pos_weight, dtype=torch.float32, device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)
    best_state = None
    best_val_exact = -1.0
    no_improve = 0
    patience = 15
    history: list[dict[str, float | int]] = []

    for epoch in range(1, training_config.num_epochs + 1):
        model.train()
        for batch_features, batch_labels in loaders["train"]:
            batch_features = batch_features.to(device)
            batch_labels = batch_labels.to(device)
            optimizer.zero_grad()
            logits = model(batch_features)
            loss = criterion(logits, batch_labels)
            loss.backward()
            optimizer.step()

        train_metrics = evaluate(model, loaders["train"], device)
        val_metrics = evaluate(model, loaders["val"], device)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_metrics["loss"],
                "train_exact_match": train_metrics["exact_match"],
                "train_bit_acc": train_metrics["bit_acc"],
                "train_pred_mean_hamming": train_metrics["pred_mean_hamming"],
                "train_zero_mask_ratio": train_metrics["pred_zero_mask_ratio"],
                "val_loss": val_metrics["loss"],
                "val_exact_match": val_metrics["exact_match"],
                "val_bit_acc": val_metrics["bit_acc"],
                "val_pred_mean_hamming": val_metrics["pred_mean_hamming"],
                "val_zero_mask_ratio": val_metrics["pred_zero_mask_ratio"],
            }
        )
        if float(val_metrics["exact_match"]) > best_val_exact:
            best_val_exact = float(val_metrics["exact_match"])
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break
        scheduler.step()

    assert best_state is not None
    model.load_state_dict(best_state)
    tuned_thresholds = optimize_thresholds(model, features[val_idx], labels[val_idx], device)
    test_metrics = evaluate(model, loaders["test"], device, tuned_thresholds)

    ambiguity_test = ambiguity[test_idx]
    clear_metrics = evaluate_subset(
        model,
        features[test_idx][ambiguity_test == 0],
        labels[test_idx][ambiguity_test == 0],
        device,
        tuned_thresholds,
    )
    ambiguous_metrics = evaluate_subset(
        model,
        features[test_idx][ambiguity_test == 1],
        labels[test_idx][ambiguity_test == 1],
        device,
        tuned_thresholds,
    )

    qat_metrics = quantized_validation(model, features[test_idx], labels[test_idx], tuned_thresholds, device)

    prefix = f"{artifact_prefix}_" if artifact_prefix else ""
    model_path = MODEL_DIR / f"{prefix}policy_{path_name}.pt"
    torch.save(model.state_dict(), model_path)

    report_path = REPORT_DIR / f"{prefix}training_{path_name}.csv"
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "epoch",
                "train_loss",
                "train_exact_match",
                "train_bit_acc",
                "train_pred_mean_hamming",
                "train_zero_mask_ratio",
                "val_loss",
                "val_exact_match",
                "val_bit_acc",
                "val_pred_mean_hamming",
                "val_zero_mask_ratio",
            ],
        )
        writer.writeheader()
        writer.writerows(history)

    summary = {
        "path": path_name,
        "artifact_prefix": artifact_prefix,
        "best_val_exact_match": best_val_exact,
        "test_loss": test_metrics["loss"],
        "test_exact_match": test_metrics["exact_match"],
        "test_bit_acc": test_metrics["bit_acc"],
        "test_pred_mean_hamming": test_metrics["pred_mean_hamming"],
        "test_true_mean_hamming": test_metrics["true_mean_hamming"],
        "test_pred_zero_mask_ratio": test_metrics["pred_zero_mask_ratio"],
        "test_true_zero_mask_ratio": test_metrics["true_zero_mask_ratio"],
        "test_bit_activation_rate": test_metrics["bit_activation_rate"],
        "pos_weight": [float(value) for value in pos_weight],
        "decision_thresholds": [float(value) for value in tuned_thresholds],
        "test_ambiguity_clear": clear_metrics,
        "test_ambiguity_ambiguous": ambiguous_metrics,
        "quantized_test": qat_metrics,
        "input_dim": model_config.input_dim,
        "hidden_dim": model_config.hidden_dim,
        "output_dim": model_config.output_dim,
        "model_path": str(model_path.relative_to(ARTIFACTS_DIR.parent)),
    }
    write_json(REPORT_DIR / f"{prefix}summary_{path_name}.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train small QEC policy networks for X/Z paths.")
    parser.add_argument("--samples", type=int, default=DatasetConfig.num_samples)
    parser.add_argument("--epochs", type=int, default=TrainingConfig.num_epochs)
    parser.add_argument("--dataset", type=Path, default=None, help="Pre-generated dataset NPZ")
    parser.add_argument("--prefix", type=str, default="", help="Artifact filename prefix")
    parser.add_argument("--x-label-key", type=str, default="x_masks")
    parser.add_argument("--z-label-key", type=str, default="z_masks")
    parser.add_argument("--hidden-dim", type=int, default=ModelConfig.hidden_dim)
    args = parser.parse_args()

    training_config = TrainingConfig(num_epochs=args.epochs)
    ensure_dirs([DATA_DIR, MODEL_DIR, REPORT_DIR])
    set_seed(training_config.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if args.dataset is not None:
        loaded = np.load(args.dataset, allow_pickle=True)
        dataset = {k: loaded[k] for k in loaded.files}
        x_labels = dataset[args.x_label_key]
        z_labels = dataset[args.z_label_key]
        ambiguity = dataset.get("ambiguity", np.zeros(len(x_labels), dtype=np.int8))
    else:
        dataset_config = DatasetConfig(num_samples=args.samples)
        dataset = generate_synthetic_dataset(dataset_config, training_config.seed)
        x_labels = dataset["x_masks"]
        z_labels = dataset["z_masks"]
        ambiguity = dataset["ambiguity"]
        np.savez(DATA_DIR / "synthetic_qec_dataset.npz", **dataset)
        dataset_meta = dict(dataset["meta"][0])
        write_json(REPORT_DIR / "dataset_quality_report.json", summarize_dataset(dataset))
        write_json(
            REPORT_DIR / "dataset_manifest.json",
            {
                "dataset": asdict(dataset_config),
                "training": asdict(training_config),
                "source": "stim.surface_code.rotated_memory",
                "trusted_sampling": dataset_meta,
                "selected_coords": [[float(value) for value in coord] for coord in dataset["selected_coords"]],
            },
        )

    model_config = ModelConfig(
        input_dim=int(dataset["x_features"].shape[1]),
        hidden_dim=args.hidden_dim,
        output_dim=int(x_labels.shape[1]),
    )
    x_summary = train_one_path(
        "x",
        dataset["z_features"],
        x_labels,
        ambiguity,
        model_config,
        training_config,
        device,
        artifact_prefix=args.prefix,
    )
    z_summary = train_one_path(
        "z",
        dataset["x_features"],
        z_labels,
        ambiguity,
        model_config,
        training_config,
        device,
        artifact_prefix=args.prefix,
    )
    prefix_str = f"{args.prefix}_" if args.prefix else ""

    # Logical error rate measurement
    x_model = PolicyMLP(model_config)
    x_model.load_state_dict(torch.load(MODEL_DIR / f"{prefix_str}policy_x.pt", map_location="cpu"))
    x_model.to(device)
    z_model = PolicyMLP(model_config)
    z_model.load_state_dict(torch.load(MODEL_DIR / f"{prefix_str}policy_z.pt", map_location="cpu"))
    z_model.to(device)
    logical_results = measure_logical_error_rate(
        x_model, z_model,
        np.array(x_summary["decision_thresholds"]),
        np.array(z_summary["decision_thresholds"]),
        device,
    )

    write_json(REPORT_DIR / f"{prefix_str}run_summary.json", {
        "x_path": x_summary,
        "z_path": z_summary,
        "logical_error_rate": logical_results,
    })


if __name__ == "__main__":
    main()
