"""Reproducible random seeding for every ML entry point (DEV_PLAN §2.5)."""

from __future__ import annotations

import os
import random

import numpy as np
import torch


def seed_everything(seed: int = 42, deterministic: bool = False) -> int:
    """Seed Python, NumPy and PyTorch RNGs.

    Args:
        seed: Value recorded with every run so results stay reproducible.
        deterministic: Force deterministic CUDA kernels. Slower; use for the
            final reported run, not for exploration.

    Returns:
        The seed, so callers can log it inline: `seed = seed_everything(cfg.seed)`.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    if deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cudnn.benchmark = False
    else:
        torch.backends.cudnn.benchmark = True

    return seed
