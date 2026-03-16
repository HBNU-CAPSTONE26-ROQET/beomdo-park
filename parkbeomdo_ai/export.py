from __future__ import annotations

import argparse
from dataclasses import asdict

import numpy as np
import torch

from .config import EXPORT_DIR, MODEL_DIR, ExportConfig, ModelConfig
from .model import PolicyMLP
from .utils import ensure_dirs, write_json


def quantize_tensor(tensor: torch.Tensor, limit: int) -> np.ndarray:
    array = tensor.detach().cpu().numpy()
    max_abs = np.max(np.abs(array))
    scale = 1.0 if max_abs == 0 else limit / max_abs
    quantized = np.clip(np.round(array * scale), -limit, limit).astype(np.int16 if limit > 127 else np.int8)
    return quantized


def write_hex(path, values: np.ndarray) -> None:
    flat = values.reshape(-1)
    with path.open("w", encoding="utf-8") as handle:
        for value in flat:
            width = 4 if values.dtype == np.int16 else 2
            handle.write(f"{int(value) & ((1 << (width * 4)) - 1):0{width}x}\n")


def export_path(path_name: str, export_config: ExportConfig) -> dict:
    state_dict = torch.load(MODEL_DIR / f"policy_{path_name}.pt", map_location="cpu")
    model_config = ModelConfig(
        input_dim=int(state_dict["layers.0.weight"].shape[1]),
        hidden_dim=int(state_dict["layers.0.weight"].shape[0]),
        output_dim=int(state_dict["layers.2.weight"].shape[0]),
    )
    model = PolicyMLP(model_config)
    model.load_state_dict(state_dict)
    state_dict = model.state_dict()

    fc1_weight = quantize_tensor(state_dict["layers.0.weight"], export_config.scale_weight)
    fc1_bias = quantize_tensor(state_dict["layers.0.bias"], export_config.scale_bias)
    fc2_weight = quantize_tensor(state_dict["layers.2.weight"], export_config.scale_weight)
    fc2_bias = quantize_tensor(state_dict["layers.2.bias"], export_config.scale_bias)

    write_hex(EXPORT_DIR / f"weights_fc1_{path_name}.hex", fc1_weight)
    write_hex(EXPORT_DIR / f"bias_fc1_{path_name}.hex", fc1_bias)
    write_hex(EXPORT_DIR / f"weights_fc2_{path_name}.hex", fc2_weight)
    write_hex(EXPORT_DIR / f"bias_fc2_{path_name}.hex", fc2_bias)

    return {
        "path": path_name,
        "input_dim": model_config.input_dim,
        "hidden_dim": model_config.hidden_dim,
        "output_dim": model_config.output_dim,
        "fc1_weight_shape": list(fc1_weight.shape),
        "fc1_bias_shape": list(fc1_bias.shape),
        "fc2_weight_shape": list(fc2_weight.shape),
        "fc2_bias_shape": list(fc2_bias.shape),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export trained policy networks to FPGA-friendly hex files.")
    parser.parse_args()
    ensure_dirs([EXPORT_DIR])
    export_config = ExportConfig()
    payload = {
        "config": asdict(export_config),
        "x_path": export_path("x", export_config),
        "z_path": export_path("z", export_config),
    }
    write_json(EXPORT_DIR / "model_manifest.json", payload)


if __name__ == "__main__":
    main()
