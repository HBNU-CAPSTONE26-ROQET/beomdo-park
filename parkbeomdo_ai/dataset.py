from __future__ import annotations

from dataclasses import asdict
from itertools import product

import numpy as np
from pymatching import Matching
import stim
import torch
from torch.utils.data import Dataset

from .config import DatasetConfig


CANONICAL_COORDS = (
    (2.0, 0.0),
    (2.0, 2.0),
    (4.0, 2.0),
    (6.0, 2.0),
    (0.0, 4.0),
    (2.0, 4.0),
    (4.0, 4.0),
    (4.0, 6.0),
)
DATA_QUBIT_COORDS = (
    (1.0, 1.0),
    (1.0, 3.0),
    (1.0, 5.0),
    (3.0, 1.0),
    (3.0, 3.0),
    (3.0, 5.0),
    (5.0, 1.0),
    (5.0, 3.0),
    (5.0, 5.0),
)


def _build_surface_code_circuit(task: str, config: DatasetConfig) -> stim.Circuit:
    return stim.Circuit.generated(
        task,
        distance=3,
        rounds=config.rounds + 1,
        after_clifford_depolarization=config.physical_error_rate,
        before_round_data_depolarization=config.physical_error_rate * 0.25,
        before_measure_flip_probability=config.physical_error_rate * 0.1,
        after_reset_flip_probability=config.physical_error_rate * 0.1,
    )


def _detector_index_map(circuit: stim.Circuit, rounds: int) -> list[int]:
    coordinates = circuit.get_detector_coordinates()
    reverse_lookup = {
        (int(round(coord[0], 0)), int(round(coord[1], 0)), int(round(coord[2], 0))): index
        for index, coord in coordinates.items()
    }

    detector_indices: list[int] = []
    for time_slice in range(1, rounds + 1):
        for x_coord, y_coord in CANONICAL_COORDS:
            key = (int(x_coord), int(y_coord), time_slice)
            detector_indices.append(reverse_lookup[key])
    return detector_indices


def _sample_detector_histories(config: DatasetConfig, task: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    circuit = _build_surface_code_circuit(task, config)
    detector_indices = _detector_index_map(circuit, config.rounds)
    sampler = circuit.compile_detector_sampler(seed=seed)
    detector_events, logical_observables = sampler.sample(
        shots=config.num_samples,
        separate_observables=True,
    )
    features = detector_events[:, detector_indices].astype(np.int8)
    observables = logical_observables.reshape(-1).astype(np.int8)
    return features, observables


def _derive_label(opposite_history: np.ndarray) -> int:
    totals = opposite_history.sum(axis=0)
    if totals.max() == 0:
        return 0
    stabilizer_index = int(np.argmax(totals))
    dominant_round = int(np.argmax(opposite_history[:, stabilizer_index]))
    qubit_index = stabilizer_index * 2 + dominant_round
    return min(qubit_index + 1, 9)


def _nearest_data_qubit(coord: tuple[float, float]) -> int:
    best_index = 0
    best_distance = float("inf")
    for index, qubit_coord in enumerate(DATA_QUBIT_COORDS):
        distance = abs(coord[0] - qubit_coord[0]) + abs(coord[1] - qubit_coord[1])
        if distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index + 1


def _project_target_to_qubits(
    coord: tuple[float, float],
    weight: float,
    top_k: int = 2,
) -> list[tuple[int, float]]:
    distances = []
    for index, qubit_coord in enumerate(DATA_QUBIT_COORDS):
        distance = abs(coord[0] - qubit_coord[0]) + abs(coord[1] - qubit_coord[1])
        closeness = 1.0 / (distance + 0.5)
        distances.append((index, closeness))

    ranked = sorted(distances, key=lambda item: item[1], reverse=True)[:top_k]
    total_closeness = sum(value for _, value in ranked)
    if total_closeness <= 0.0:
        return []
    return [(index, weight * value / total_closeness) for index, value in ranked]


def _votes_from_matched_pairs(
    matched_pairs: np.ndarray,
    selected_features: np.ndarray,
    detector_indices: list[int],
    coordinates: dict[int, list[float]],
) -> np.ndarray:
    votes = np.zeros(9, dtype=np.float32)
    if np.count_nonzero(selected_features) == 0:
        return votes

    selected_set = set(detector_indices)
    touched = False
    for det_a, det_b in matched_pairs:
        if det_a == -1 and det_b == -1:
            continue
        involved = [det for det in (int(det_a), int(det_b)) if det != -1 and det in selected_set]
        if not involved:
            continue
        touched = True
        weight = 1.0

        if det_a != -1 and det_b != -1 and det_a in selected_set and det_b in selected_set:
            coord_a = coordinates[int(det_a)]
            coord_b = coordinates[int(det_b)]
            target_coord = ((coord_a[0] + coord_b[0]) / 2.0, (coord_a[1] + coord_b[1]) / 2.0)
            weight = 1.5
        else:
            coord = coordinates[involved[0]]
            target_coord = (coord[0], coord[1])

        for qubit_index, contribution in _project_target_to_qubits(target_coord, weight):
            votes[qubit_index] += contribution

    if not touched:
        fallback_label = _derive_label(selected_features.reshape(-1, len(CANONICAL_COORDS)))
        if fallback_label > 0:
            votes[fallback_label - 1] = 1.0
    return votes


def _mask_from_votes(votes: np.ndarray, active_feature_count: int) -> np.ndarray:
    mask = np.zeros(9, dtype=np.int8)
    if float(votes.max()) <= 0.0:
        return mask

    ranked = np.argsort(-votes)
    first = int(ranked[0])
    mask[first] = 1

    if len(ranked) > 1:
        second = int(ranked[1])
        top_vote = float(votes[first])
        second_vote = float(votes[second])
        if active_feature_count >= 2 and second_vote >= 0.5 and second_vote >= top_vote * 0.85:
            mask[second] = 1

    return mask


def _ambiguity_from_votes(
    votes: np.ndarray,
    active_feature_count: int,
    baseline_prediction: int,
    logical_observable: int,
) -> int:
    ranked_votes = np.sort(votes)[::-1]
    top_vote = float(ranked_votes[0]) if len(ranked_votes) > 0 else 0.0
    second_vote = float(ranked_votes[1]) if len(ranked_votes) > 1 else 0.0
    close_competition = second_vote >= max(1.0, top_vote * 0.85)
    dense_input = active_feature_count >= 12
    baseline_mismatch = int(baseline_prediction) != int(logical_observable)
    return int(close_competition or (dense_input and baseline_mismatch))


def _mapping_trace_summary() -> dict[str, object]:
    single_targets = {index: [] for index in range(len(DATA_QUBIT_COORDS))}
    pair_targets = {index: [] for index in range(len(DATA_QUBIT_COORDS))}

    for detector_index, coord in enumerate(CANONICAL_COORDS):
        for qubit_index, contribution in _project_target_to_qubits(coord, 1.0):
            single_targets[qubit_index].append(
                {
                    "detector_index": detector_index,
                    "coord": [float(coord[0]), float(coord[1])],
                    "weight": float(contribution),
                }
            )

    for index_a, index_b in product(range(len(CANONICAL_COORDS)), repeat=2):
        coord_a = CANONICAL_COORDS[index_a]
        coord_b = CANONICAL_COORDS[index_b]
        midpoint = ((coord_a[0] + coord_b[0]) / 2.0, (coord_a[1] + coord_b[1]) / 2.0)
        for qubit_index, contribution in _project_target_to_qubits(midpoint, 1.0):
            pair_targets[qubit_index].append(
                {
                    "pair": [index_a, index_b],
                    "midpoint": [float(midpoint[0]), float(midpoint[1])],
                    "weight": float(contribution),
                }
            )

    single_supported = [index for index, values in single_targets.items() if values]
    pair_supported = [index for index, values in pair_targets.items() if values]
    pair_only = [index for index in pair_supported if index not in single_supported]
    unreachable = [index for index in range(len(DATA_QUBIT_COORDS)) if not single_targets[index] and not pair_targets[index]]

    return {
        "single_detector_supported_qubits": single_supported,
        "pair_midpoint_supported_qubits": pair_supported,
        "pair_midpoint_only_qubits": pair_only,
        "unreachable_qubits": unreachable,
        "single_detector_examples": {
            str(index): values[:4] for index, values in single_targets.items() if values
        },
        "pair_midpoint_examples": {
            str(index): values[:4] for index, values in pair_targets.items() if values
        },
    }


def _sample_trusted_batch(
    sampler: stim.CompiledDetectorSampler,
    matching: Matching,
    shots: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    detector_events, logical_observables = sampler.sample(
        shots=shots,
        separate_observables=True,
    )
    decoder_predictions = matching.decode_batch(detector_events).reshape(-1).astype(np.int8)
    observables = logical_observables.reshape(-1).astype(np.int8)
    accepted = decoder_predictions == observables
    return detector_events[accepted], observables[accepted], decoder_predictions[accepted]


def _sample_task_with_labels(
    config: DatasetConfig,
    task: str,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, int]:
    circuit = _build_surface_code_circuit(task, config)
    detector_indices = _detector_index_map(circuit, config.rounds)
    coordinates = circuit.get_detector_coordinates()
    sampler = circuit.compile_detector_sampler(seed=seed)
    matching = Matching.from_detector_error_model(circuit.detector_error_model(decompose_errors=True))
    accepted_events: list[np.ndarray] = []
    accepted_observables: list[np.ndarray] = []
    accepted_predictions: list[np.ndarray] = []
    total_sampled = 0
    total_accepted = 0

    while total_accepted < config.num_samples:
        remaining = config.num_samples - total_accepted
        batch_shots = max(remaining * 2, 256)
        batch_events, batch_observables, batch_predictions = _sample_trusted_batch(
            sampler,
            matching,
            batch_shots,
        )
        total_sampled += batch_shots
        if len(batch_observables) == 0:
            continue
        accepted_events.append(batch_events)
        accepted_observables.append(batch_observables)
        accepted_predictions.append(batch_predictions)
        total_accepted += int(len(batch_observables))

    detector_events = np.concatenate(accepted_events, axis=0)[: config.num_samples]
    observables = np.concatenate(accepted_observables, axis=0)[: config.num_samples]
    decoder_predictions = np.concatenate(accepted_predictions, axis=0)[: config.num_samples]
    selected_features = detector_events[:, detector_indices].astype(np.int8)
    masks = np.zeros((config.num_samples, 9), dtype=np.int8)
    vote_maps = np.zeros((config.num_samples, 9), dtype=np.float32)

    for shot_index in range(config.num_samples):
        matched_pairs = matching.decode_to_matched_dets_array(detector_events[shot_index])
        vote_maps[shot_index] = _votes_from_matched_pairs(
            matched_pairs,
            selected_features[shot_index],
            detector_indices,
            coordinates,
        )
        masks[shot_index] = _mask_from_votes(
            vote_maps[shot_index],
            int(np.count_nonzero(selected_features[shot_index])),
        )

    acceptance_rate = total_accepted / max(total_sampled, 1)
    return selected_features, observables, masks, decoder_predictions, vote_maps, acceptance_rate, total_sampled


def generate_synthetic_dataset(config: DatasetConfig, seed: int) -> dict[str, np.ndarray]:
    x_features, logical_z, z_masks, baseline_z_obs, z_vote_maps, z_acceptance_rate, z_total_sampled = _sample_task_with_labels(
        config,
        "surface_code:rotated_memory_x",
        seed + 11,
    )
    z_features, logical_x, x_masks, baseline_x_obs, x_vote_maps, x_acceptance_rate, x_total_sampled = _sample_task_with_labels(
        config,
        "surface_code:rotated_memory_z",
        seed + 29,
    )
    ambiguity = np.zeros((config.num_samples,), dtype=np.int8)

    for index in range(config.num_samples):
        x_hist = x_features[index].reshape(config.rounds, config.num_stabilizers)
        z_hist = z_features[index].reshape(config.rounds, config.num_stabilizers)
        ambiguity[index] = int(
            _ambiguity_from_votes(
                x_vote_maps[index],
                int(np.count_nonzero(z_hist)),
                int(baseline_x_obs[index]),
                int(logical_x[index]),
            )
            or _ambiguity_from_votes(
                z_vote_maps[index],
                int(np.count_nonzero(x_hist)),
                int(baseline_z_obs[index]),
                int(logical_z[index]),
            )
        )

    x_vote_usage = (x_vote_maps > 0).mean(axis=0).astype(np.float32)
    z_vote_usage = (z_vote_maps > 0).mean(axis=0).astype(np.float32)
    mapping_trace = _mapping_trace_summary()

    return {
        "x_features": x_features,
        "z_features": z_features,
        "x_masks": x_masks,
        "z_masks": z_masks,
        "ambiguity": ambiguity,
        "logical_x": logical_x,
        "logical_z": logical_z,
        "baseline_x_obs": baseline_x_obs,
        "baseline_z_obs": baseline_z_obs,
        "x_vote_maps": x_vote_maps,
        "z_vote_maps": z_vote_maps,
        "x_vote_usage": x_vote_usage,
        "z_vote_usage": z_vote_usage,
        "x_acceptance_rate": np.array([x_acceptance_rate], dtype=np.float32),
        "z_acceptance_rate": np.array([z_acceptance_rate], dtype=np.float32),
        "x_total_sampled": np.array([x_total_sampled], dtype=np.int32),
        "z_total_sampled": np.array([z_total_sampled], dtype=np.int32),
        "selected_coords": np.array(CANONICAL_COORDS, dtype=np.float32),
        "meta": np.array(
            [
                {
                    **asdict(config),
                    "trusted_samples_only": True,
                    "x_acceptance_rate": x_acceptance_rate,
                    "z_acceptance_rate": z_acceptance_rate,
                    "x_total_sampled": x_total_sampled,
                    "z_total_sampled": z_total_sampled,
                    "mapping_trace": mapping_trace,
                }
            ],
            dtype=object,
        ),
    }


class QECPathDataset(Dataset):
    def __init__(self, features: np.ndarray, labels: np.ndarray):
        self.features = torch.tensor(features, dtype=torch.float32)
        self.labels = torch.tensor(labels, dtype=torch.float32)

    def __len__(self) -> int:
        return int(self.labels.shape[0])

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.features[index], self.labels[index]
