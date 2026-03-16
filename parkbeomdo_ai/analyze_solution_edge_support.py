from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import stim
from pymatching import Matching

from .config import REPORT_DIR, DatasetConfig, TrainingConfig
from .dataset import DATA_QUBIT_COORDS, _build_surface_code_circuit, _sample_trusted_batch
from .utils import ensure_dirs, write_json


COORD_RE = re.compile(r"coords ([^\]]+)")
DATA_COORD_TO_INDEX = {
    tuple(map(float, coord)): index for index, coord in enumerate(DATA_QUBIT_COORDS)
}


def _extract_data_support_from_location_text(location_text: str) -> set[int]:
    support: set[int] = set()
    for match in COORD_RE.finditer(location_text):
        values = tuple(float(value.strip()) for value in match.group(1).split(","))
        if len(values) != 2:
            continue
        if values in DATA_COORD_TO_INDEX:
            support.add(DATA_COORD_TO_INDEX[values])
    return support


def _mask_from_support(indices: set[int]) -> list[int]:
    mask = [0] * len(DATA_QUBIT_COORDS)
    for index in indices:
        mask[index] = 1
    return mask


def _boundary_filters(node: int) -> list[str]:
    return [f"error(1) D{node}", f"error(1) D{node} L0"]


def _edge_filters(node1: int, node2: int | None) -> list[str]:
    if node2 is None:
        return _boundary_filters(node1)
    left, right = sorted((node1, node2))
    return [f"error(1) D{left} D{right}"]


def _edge_key(node1: int, node2: int | None) -> str:
    if node2 is None:
        return f"{node1}|B"
    left, right = sorted((node1, node2))
    return f"{left}|{right}"


def _build_edge_support_map(circuit: stim.Circuit, matching: Matching) -> dict[str, dict[str, object]]:
    edge_map: dict[str, dict[str, object]] = {}
    for node1, node2, _ in matching.edges():
        key = _edge_key(int(node1), None if node2 is None else int(node2))
        location_supports: list[set[int]] = []
        successful_filters: list[str] = []
        for filter_text in _edge_filters(node1, node2):
            try:
                explained = circuit.explain_detector_error_model_errors(
                    dem_filter=stim.DetectorErrorModel(filter_text),
                    reduce_to_one_representative_error=False,
                )
            except ValueError:
                continue
            if not explained:
                continue
            successful_filters.append(filter_text)
            for item in explained:
                for location in item.circuit_error_locations:
                    location_supports.append(_extract_data_support_from_location_text(str(location)))

        non_empty_supports = [support for support in location_supports if support]
        support_union = set().union(*non_empty_supports) if non_empty_supports else set()
        if non_empty_supports:
            support_intersection = set(non_empty_supports[0])
            for support in non_empty_supports[1:]:
                support_intersection &= support
        else:
            support_intersection = set()

        support_histogram = Counter(index for support in non_empty_supports for index in support)
        edge_map[key] = {
            "nodes": [int(node1), None if node2 is None else int(node2)],
            "filters": successful_filters,
            "num_location_supports": len(location_supports),
            "num_non_empty_supports": len(non_empty_supports),
            "support_union": sorted(support_union),
            "support_intersection": sorted(support_intersection),
            "support_union_mask": _mask_from_support(support_union),
            "support_intersection_mask": _mask_from_support(support_intersection),
            "support_frequency": {str(index): int(count) for index, count in sorted(support_histogram.items())},
        }
    return edge_map


def _aggregate_mask_statistics(masks: np.ndarray) -> dict[str, object]:
    if len(masks) == 0:
        return {
            "sample_count": 0,
            "bit_activation": [0.0] * len(DATA_QUBIT_COORDS),
            "dead_bits": list(range(len(DATA_QUBIT_COORDS))),
            "hamming_distribution": {},
            "mean_hamming": 0.0,
        }

    hamming = masks.sum(axis=1).astype(int)
    bit_activation = masks.mean(axis=0)
    return {
        "sample_count": int(len(masks)),
        "bit_activation": [float(value) for value in bit_activation],
        "dead_bits": [int(index) for index, value in enumerate(bit_activation) if value == 0.0],
        "hamming_distribution": {str(key): int(value) for key, value in sorted(Counter(hamming.tolist()).items())},
        "mean_hamming": float(np.mean(hamming)),
    }


def _sample_solution_masks(
    circuit: stim.Circuit,
    matching: Matching,
    edge_support_map: dict[str, dict[str, object]],
    num_samples: int,
    seed: int,
) -> dict[str, object]:
    sampler = circuit.compile_detector_sampler(seed=seed)
    accepted_events: list[np.ndarray] = []
    total_accepted = 0
    total_sampled = 0
    while total_accepted < num_samples:
        remaining = num_samples - total_accepted
        batch_shots = max(remaining * 2, 256)
        batch_events, _, _ = _sample_trusted_batch(sampler, matching, batch_shots)
        total_sampled += batch_shots
        if len(batch_events) == 0:
            continue
        accepted_events.append(batch_events)
        total_accepted += int(len(batch_events))

    detector_events = np.concatenate(accepted_events, axis=0)[:num_samples]
    union_masks = np.zeros((num_samples, len(DATA_QUBIT_COORDS)), dtype=np.int8)
    intersection_masks = np.zeros_like(union_masks)
    unmatched_edges = 0

    for shot_index in range(num_samples):
        solution_edges = matching.decode_to_edges_array(detector_events[shot_index])
        union_support: set[int] = set()
        intersection_support: set[int] = set()
        for node1, node2 in solution_edges:
            key = _edge_key(int(node1), None if int(node2) == -1 else int(node2))
            payload = edge_support_map.get(key)
            if payload is None:
                unmatched_edges += 1
                continue
            union_support.update(int(index) for index in payload["support_union"])
            intersection_support.update(int(index) for index in payload["support_intersection"])
        union_masks[shot_index] = np.array(_mask_from_support(union_support), dtype=np.int8)
        intersection_masks[shot_index] = np.array(_mask_from_support(intersection_support), dtype=np.int8)

    return {
        "acceptance_rate": float(total_accepted / max(total_sampled, 1)),
        "union_mask_stats": _aggregate_mask_statistics(union_masks),
        "intersection_mask_stats": _aggregate_mask_statistics(intersection_masks),
        "unmatched_edges": int(unmatched_edges),
    }


def analyze_task(task: str, num_samples: int, seed: int) -> dict[str, object]:
    circuit = _build_surface_code_circuit(task, DatasetConfig())
    matching = Matching.from_detector_error_model(circuit.detector_error_model(decompose_errors=True))
    edge_support_map = _build_edge_support_map(circuit, matching)

    edges_with_union_support = sum(1 for payload in edge_support_map.values() if payload["support_union"])
    edges_with_intersection_support = sum(1 for payload in edge_support_map.values() if payload["support_intersection"])

    payload = {
        "task": task,
        "graph_edge_count": int(len(edge_support_map)),
        "edges_with_union_support": int(edges_with_union_support),
        "edges_with_intersection_support": int(edges_with_intersection_support),
        "sampled_solution_support": _sample_solution_masks(circuit, matching, edge_support_map, num_samples, seed),
        "representative_edges": {
            key: value for key, value in list(edge_support_map.items())[:20]
        },
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze decoder solution edges and their data-qubit support inferred from Stim explanations.")
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=TrainingConfig.seed)
    args = parser.parse_args()

    ensure_dirs([REPORT_DIR])
    payload = {
        "x_path": analyze_task("surface_code:rotated_memory_x", args.samples, args.seed + 101),
        "z_path": analyze_task("surface_code:rotated_memory_z", args.samples, args.seed + 151),
    }
    write_json(REPORT_DIR / "solution_edge_support_analysis.json", payload)


if __name__ == "__main__":
    main()