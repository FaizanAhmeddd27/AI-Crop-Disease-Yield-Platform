"""Model export, optimization, and numerical parity verification.

Fulfills DEV_PLAN Task 2.12 (ML-006, ML-007).
Exports PyTorch weights to:
1. TorchScript (`model.pt`)
2. ONNX (`model.onnx`)
Verifies that logits match between original and exported models within tolerance (1e-4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import torch
import torch.nn as nn

from .models import build_disease_model


def export_to_torchscript(
    model: nn.Module,
    save_path: Path | str,
    dummy_input: torch.Tensor,
) -> Path:
    """Trace and save model as TorchScript artifact."""
    model.eval()
    traced = torch.jit.trace(model, dummy_input)
    traced.save(str(save_path))
    return Path(save_path)


def export_to_onnx(
    model: nn.Module,
    save_path: Path | str,
    dummy_input: torch.Tensor,
    input_names: Tuple[str] = ("input",),
    output_names: Tuple[str] = ("logits",),
) -> Path:
    """Export PyTorch model to ONNX runtime format."""
    model.eval()
    torch.onnx.export(
        model,
        dummy_input,
        str(save_path),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=list(input_names),
        output_names=list(output_names),
        dynamic_axes={"input": {0: "batch_size"}, "logits": {0: "batch_size"}},
    )
    return Path(save_path)


def verify_export_parity(
    original_model: nn.Module,
    exported_path: Path | str,
    dummy_input: torch.Tensor,
    tolerance: float = 1e-4,
) -> Tuple[bool, float]:
    """Test numerical parity between original model and exported TorchScript/ONNX artifact.

    Returns:
        (is_valid, max_absolute_error)
    """
    original_model.eval()
    with torch.no_grad():
        expected_logits = original_model(dummy_input).numpy()

    exp_path = Path(exported_path)
    if exp_path.suffix == ".pt":
        loaded = torch.jit.load(str(exp_path))
        loaded.eval()
        with torch.no_grad():
            actual_logits = loaded(dummy_input).numpy()
    elif exp_path.suffix == ".onnx":
        import onnxruntime as ort

        sess = ort.InferenceSession(str(exp_path), providers=["CPUExecutionProvider"])
        input_name = sess.get_inputs()[0].name
        actual_logits = sess.run(None, {input_name: dummy_input.numpy()})[0]
    else:
        raise ValueError(f"Unsupported artifact type: {exp_path.suffix}")

    max_err = float(np.max(np.abs(expected_logits - actual_logits)))
    is_valid = max_err <= tolerance
    return is_valid, round(max_err, 6)


if __name__ == "__main__":
    print("Testing TorchScript export and parity verification...")
    dummy_model = build_disease_model("baseline_cnn", num_classes=38, pretrained=False)
    test_input = torch.randn(1, 3, 224, 224)
    tmp_path = Path("test_model.pt")

    export_to_torchscript(dummy_model, tmp_path, test_input)
    passed, err = verify_export_parity(dummy_model, tmp_path, test_input)
    print(f"Parity Test Passed: {passed} (Max Logit Error: {err})")
    assert passed, "Export parity check failed"

    if tmp_path.exists():
        tmp_path.unlink()
    print("Export module verified.")
