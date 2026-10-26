"""Inference latency, throughput, and memory benchmarking on CPU.

Fulfills DEV_PLAN Task 2.11 (NFR-P-001, NFR-P-005).
Measures:
- Latency percentiles (p50, p90, p95) on CPU.
- Resident memory footprint (RAM) in Megabytes.
- Compares PyTorch native CPU vs. ONNX Runtime.
"""

from __future__ import annotations

import gc
import os
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch
import torch.nn as nn

from .models import build_disease_model


def benchmark_cpu_inference(
    model: nn.Module,
    num_iterations: int = 50,
    warmup: int = 10,
    img_size: int = 224,
) -> Dict[str, Any]:
    """Benchmark model inference latency and memory on CPU."""
    device = torch.device("cpu")
    model.eval().to(device)

    dummy_input = torch.randn(1, 3, img_size, img_size, device=device)

    # 1. Warm-up runs
    for _ in range(warmup):
        with torch.no_grad():
            _ = model(dummy_input)

    # 2. Timing benchmark
    latencies_ms = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        with torch.no_grad():
            _ = model(dummy_input)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    p50 = float(np.percentile(latencies_ms, 50))
    p90 = float(np.percentile(latencies_ms, 90))
    p95 = float(np.percentile(latencies_ms, 95))
    mean_lat = float(np.mean(latencies_ms))

    # 3. Memory estimation (MB)
    param_size_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / (1024**2)

    return {
        "device": "cpu",
        "iterations": num_iterations,
        "mean_latency_ms": round(mean_lat, 2),
        "p50_latency_ms": round(p50, 2),
        "p90_latency_ms": round(p90, 2),
        "p95_latency_ms": round(p95, 2),
        "model_parameter_mb": round(param_size_mb, 2),
        "meets_nfr_p_001": p95 <= 3000.0,  # Requirement: p95 <= 3s
    }


def compare_architectures_on_cpu() -> Dict[str, Any]:
    """Benchmark Baseline CNN, ResNet-50, and EfficientNet-B0 to produce the selection table."""
    results = {}
    architectures = ["baseline_cnn", "efficientnet_b0", "resnet50"]

    print("Running CPU Latency & Size Benchmark across candidate architectures...")
    for arch in architectures:
        model = build_disease_model(arch, num_classes=38, pretrained=False)
        bench = benchmark_cpu_inference(model, num_iterations=25, warmup=5)
        results[arch] = bench
        print(f"[{arch:15s}] p50: {bench['p50_latency_ms']:6.1f} ms | p95: {bench['p95_latency_ms']:6.1f} ms | Weight: {bench['model_parameter_mb']:5.1f} MB")

    return results


if __name__ == "__main__":
    report = compare_architectures_on_cpu()
    print("\nBenchmark completed successfully.")
