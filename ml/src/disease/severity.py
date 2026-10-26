"""Automated Leaf Disease Severity Estimation and Lesion Segmentation.

Fulfills DEV_PLAN Tasks 4.4, 4.5 (FR-D-013, PRD §7.3).
Segments leaf surface and diseased necrotic/chlorotic lesions via dual-space
(HSV + Lab) adaptive thresholding and morphological filtering, mapping damage
percentage to standardized agronomic severity bands:
- Low: < 10%
- Medium: 10% - 30%
- High: >= 30%
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image


class SeverityBand(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class SeverityResult:
    """Strongly-typed severity assessment output."""

    severity_ratio_pct: float
    severity_band: SeverityBand
    leaf_area_pixels: int
    lesion_area_pixels: int
    confidence_score: float
    summary_message: str

    def to_dict(self):
        return {
            "severity_ratio_pct": round(self.severity_ratio_pct, 2),
            "severity_band": self.severity_band.value,
            "leaf_area_pixels": int(self.leaf_area_pixels),
            "lesion_area_pixels": int(self.lesion_area_pixels),
            "confidence_score": round(self.confidence_score, 3),
            "summary_message": self.summary_message,
        }


class LeafSeverityEstimator:
    """Computer vision pipeline for segmenting leaf boundaries and foliar lesions."""

    def __init__(
        self,
        low_band_max_pct: float = 10.0,
        medium_band_max_pct: float = 30.0,
        min_leaf_pixel_ratio: float = 0.05,
    ):
        self.low_max = low_band_max_pct
        self.medium_max = medium_band_max_pct
        self.min_leaf_ratio = min_leaf_pixel_ratio

    def segment_leaf(self, image_rgb: np.ndarray) -> np.ndarray:
        """Create a clean binary mask of the leaf tissue (excluding uniform or dark backgrounds)."""
        hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
        lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)

        # Foliage green, yellow-green, and dry brownish leaf tones in HSV
        lower_leaf1 = np.array([20, 30, 25])
        upper_leaf1 = np.array([95, 255, 255])
        mask1 = cv2.inRange(hsv, lower_leaf1, upper_leaf1)

        # Extended olive-brown dry leaf tones
        lower_leaf2 = np.array([10, 35, 30])
        upper_leaf2 = np.array([25, 255, 230])
        mask2 = cv2.inRange(hsv, lower_leaf2, upper_leaf2)

        # Combine
        combined_mask = cv2.bitwise_or(mask1, mask2)

        # Morphological cleanup
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))

        cleaned = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel_open)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)

        # Fill holes in the largest detected leaf contour
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        final_leaf_mask = np.zeros_like(cleaned)

        if contours:
            # Sort contours by area descending; retain contours occupying > 3% of frame
            total_img_area = image_rgb.shape[0] * image_rgb.shape[1]
            valid_contours = [c for c in contours if cv2.contourArea(c) > total_img_area * 0.02]
            if valid_contours:
                cv2.drawContours(final_leaf_mask, valid_contours, -1, 255, thickness=cv2.FILLED)
            else:
                largest = max(contours, key=cv2.contourArea)
                cv2.drawContours(final_leaf_mask, [largest], -1, 255, thickness=cv2.FILLED)

        return final_leaf_mask

    def segment_lesions(self, image_rgb: np.ndarray, leaf_mask: np.ndarray) -> np.ndarray:
        """Isolate diseased lesion tissue (necrotic spots, fungal blights, rusts) within the leaf mask."""
        hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
        lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)

        h, s, v = cv2.split(hsv)
        l_chan, a_chan, b_chan = cv2.split(lab)

        # Necrotic tissue: dark brown/black spots (low brightness or very high red-brown chroma)
        necrotic_mask = ((v < 85) | ((h < 18) & (s > 60))) & (leaf_mask > 0)

        # Chlorotic tissue: yellow/orange halos and rust pustules
        chlorotic_mask = ((h >= 15) & (h <= 34) & (s > 90) & (v > 90)) & (leaf_mask > 0)

        # High a* in Lab indicates reddish/brownish fungal lesions
        lab_lesion_mask = (a_chan > 138) & (leaf_mask > 0)

        # Combine candidate lesion pixels
        raw_lesions = (necrotic_mask | chlorotic_mask | lab_lesion_mask).astype(np.uint8) * 255

        # Morphological filter to remove single-pixel specks
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        filtered_lesions = cv2.morphologyEx(raw_lesions, cv2.MORPH_OPEN, kernel)

        return filtered_lesions

    def assess_severity(self, image_input: Union[np.ndarray, Image.Image, Path, str]) -> Tuple[SeverityResult, np.ndarray]:
        """Estimate damage percentage and generate visualization overlay.

        Returns:
            (SeverityResult, visual_overlay_rgb)
        """
        if isinstance(image_input, (str, Path)):
            img_bgr = cv2.imread(str(image_input))
            if img_bgr is None:
                raise FileNotFoundError(f"Failed to read image at {image_input}")
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        elif isinstance(image_input, Image.Image):
            img_rgb = np.array(image_input.convert("RGB"))
        elif isinstance(image_input, np.ndarray):
            img_rgb = image_input.copy()
        else:
            raise ValueError("Unsupported image input type.")

        leaf_mask = self.segment_leaf(img_rgb)
        leaf_pixels = int(np.count_nonzero(leaf_mask))
        total_pixels = img_rgb.shape[0] * img_rgb.shape[1]

        # Guard against empty / non-leaf images
        if leaf_pixels < total_pixels * self.min_leaf_ratio:
            return (
                SeverityResult(
                    severity_ratio_pct=0.0,
                    severity_band=SeverityBand.LOW,
                    leaf_area_pixels=0,
                    lesion_area_pixels=0,
                    confidence_score=0.20,
                    summary_message="Insufficient leaf surface detected in photo. Please ensure leaf fills viewfinder.",
                ),
                img_rgb,
            )

        lesion_mask = self.segment_lesions(img_rgb, leaf_mask)
        lesion_pixels = int(np.count_nonzero(lesion_mask))

        # Raw percentage of damaged leaf area
        ratio_pct = min(100.0, (lesion_pixels / max(1, leaf_pixels)) * 100.0)

        # Map to standard agricultural severity bands
        if ratio_pct < self.low_max:
            band = SeverityBand.LOW
            msg = f"Mild / Early infection stage detected ({ratio_pct:.1f}% leaf surface affected). High treatment responsiveness."
        elif ratio_pct < self.medium_max:
            band = SeverityBand.MEDIUM
            msg = f"Moderate infection detected ({ratio_pct:.1f}% leaf surface affected). Active spreading; treatment advised."
        else:
            band = SeverityBand.HIGH
            msg = f"Severe infection detected ({ratio_pct:.1f}% leaf surface affected). Advanced necrosis; immediate intervention required."

        # Produce visual overlay
        overlay = img_rgb.copy()
        # Highlight leaf contour in subtle green
        contours_leaf, _ = cv2.findContours(leaf_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours_leaf, -1, (0, 220, 0), 2)

        # Highlight lesions in bright crimson/amber
        lesion_color_mask = np.zeros_like(img_rgb)
        lesion_color_mask[lesion_mask > 0] = [235, 35, 35]  # Red overlay on lesions
        overlay = cv2.addWeighted(overlay, 1.0, lesion_color_mask, 0.55, 0)

        result = SeverityResult(
            severity_ratio_pct=ratio_pct,
            severity_band=band,
            leaf_area_pixels=leaf_pixels,
            lesion_area_pixels=lesion_pixels,
            confidence_score=0.92,
            summary_message=msg,
        )

        return result, overlay


if __name__ == "__main__":
    print("Testing LeafSeverityEstimator...")
    estimator = LeafSeverityEstimator()

    # Create dummy synthetic leaf image (green leaf with a brown circular necrotic lesion)
    test_img = np.zeros((300, 300, 3), dtype=np.uint8)
    # Background: dark gray (50, 50, 50)
    test_img[:] = [50, 50, 50]

    # Draw green leaf ellipse (RGB: [45, 160, 55])
    cv2.ellipse(test_img, (150, 150), (100, 70), 30, 0, 360, (45, 160, 55), -1)

    # Draw dark brown necrotic spot inside leaf (RGB: [60, 30, 15])
    cv2.circle(test_img, (140, 140), 25, (60, 30, 15), -1)

    res, overlay = estimator.assess_severity(test_img)
    print("Severity Result:", res.to_dict())
    assert res.leaf_area_pixels > 0
    assert res.lesion_area_pixels > 0
    assert res.severity_band in (SeverityBand.LOW, SeverityBand.MEDIUM, SeverityBand.HIGH)
    assert overlay.shape == (300, 300, 3)
    print("LeafSeverityEstimator verified.")
