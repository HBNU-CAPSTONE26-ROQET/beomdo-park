from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import stim

from .config import REPORT_DIR, DatasetConfig
from .dataset import CANONICAL_COORDS, DATA_QUBIT_COORDS, _build_surface_code_circuit
from .utils import ensure_dirs, write_json


COORD_RE = re.compile(r"coords ([^\]]+)")


def _normalize_dem_line(line: str) -> str:
    head, tail = line.split(")", 1)
    return f"error(1){tail}"


def _extract_2d_coords(text: str) -> set[tuple[float, float]]:
    coords: set[tuple[float, float]] = set()
    for match in COORD_RE.finditer(text):
        values = tuple(float(value.strip()) for value in match.group(1).split(","))
        if len(values) == 2:
            coords.add(values)
    return coords


def _classify_coords(coords: set[tuple[float, float]]) -> str:
    if not coords:
        return "unknown"

    data_coords = {tuple(map(float, coord)) for coord in DATA_QUBIT_COORDS}
    ancilla_coords = {tuple(map(float, coord)) for coord in CANONICAL_COORDS}
    if coords.issubset(data_coords):
        return "data"
    if coords.issubset(ancilla_coords):
        return "ancilla"
    return "mixed"


def analyze_task(task: str, config: DatasetConfig, sample_limit: int | None = None) -> dict[str, object]:
    circuit = _build_surface_code_circuit(task, config)
    dem = circuit.detector_error_model(decompose_errors=True)
    all_lines = str(dem).splitlines()
    lines = [line.strip() for line in all_lines if line.strip().startswith("error(")]
    if sample_limit is not None:
        lines = lines[:sample_limit]

    category_counts: Counter[str] = Counter()
    representative_examples: dict[str, list[dict[str, object]]] = {
        "data": [],
        "ancilla": [],
        "mixed": [],
        "unknown": [],
    }
    multi_location_terms = 0

    for line in lines:
        explained = circuit.explain_detector_error_model_errors(
            dem_filter=stim.DetectorErrorModel(_normalize_dem_line(line)),
            reduce_to_one_representative_error=False,
        )
        if not explained:
            category = "unknown"
            location_count = 0
            coords = set()
            location_preview: list[str] = []
        else:
            item = explained[0]
            location_texts = [str(location) for location in item.circuit_error_locations]
            coords = set()
            for location_text in location_texts:
                coords.update(_extract_2d_coords(location_text))
            category = _classify_coords(coords)
            location_count = len(location_texts)
            location_preview = location_texts[:3]
            if location_count > 1:
                multi_location_terms += 1

        category_counts[category] += 1
        if len(representative_examples[category]) < 5:
            representative_examples[category].append(
                {
                    "dem_term": line,
                    "coords": [list(coord) for coord in sorted(coords)],
                    "location_count": location_count,
                    "locations": location_preview,
                }
            )

    qubit_coords = {
        str(index): [float(value) for value in coord]
        for index, coord in sorted(circuit.get_final_qubit_coordinates().items())
    }

    return {
        "task": task,
        "num_dem_terms_analyzed": len(lines),
        "num_total_dem_terms": len(all_lines),
        "num_error_terms": len([line for line in all_lines if line.strip().startswith("error(")]),
        "num_qubits": len(qubit_coords),
        "qubit_coords": qubit_coords,
        "data_qubit_coords": [list(map(float, coord)) for coord in DATA_QUBIT_COORDS],
        "ancilla_coords": [list(map(float, coord)) for coord in CANONICAL_COORDS],
        "category_counts": dict(category_counts),
        "multi_location_terms": multi_location_terms,
        "representative_examples": representative_examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze how Stim detector error model terms map back to circuit fault locations.")
    parser.add_argument("--sample-limit", type=int, default=None)
    args = parser.parse_args()

    config = DatasetConfig()
    ensure_dirs([REPORT_DIR])
    payload = {
        "x_path": analyze_task("surface_code:rotated_memory_x", config, args.sample_limit),
        "z_path": analyze_task("surface_code:rotated_memory_z", config, args.sample_limit),
    }
    write_json(REPORT_DIR / "dem_mapping_analysis.json", payload)


if __name__ == "__main__":
    main()