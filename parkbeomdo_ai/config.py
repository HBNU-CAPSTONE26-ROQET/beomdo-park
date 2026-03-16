from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelConfig:
    input_dim: int = 24
    hidden_dim: int = 32
    output_dim: int = 9


@dataclass(frozen=True)
class TrainingConfig:
    seed: int = 7
    num_epochs: int = 50
    batch_size: int = 64
    learning_rate: float = 1e-3
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15


@dataclass(frozen=True)
class DatasetConfig:
    num_samples: int = 20000
    physical_error_rate: float = 0.02
    rounds: int = 3
    num_data_qubits: int = 9
    num_stabilizers: int = 8


@dataclass(frozen=True)
class ExportConfig:
    scale_weight: int = 127
    scale_activation: int = 127
    scale_bias: int = 1024


ROOT_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
DATA_DIR = ARTIFACTS_DIR / "data"
MODEL_DIR = ARTIFACTS_DIR / "models"
EXPORT_DIR = ARTIFACTS_DIR / "export"
REPORT_DIR = ARTIFACTS_DIR / "reports"
