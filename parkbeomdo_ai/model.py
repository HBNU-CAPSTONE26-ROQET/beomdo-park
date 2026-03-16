from __future__ import annotations

import torch
from torch import nn

from .config import ModelConfig


class PolicyMLP(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(config.input_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, config.output_dim),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.layers(inputs)


def logits_to_mask(logits: torch.Tensor, threshold: float = 0.0) -> torch.Tensor:
    return (logits >= threshold).to(dtype=torch.int64)
