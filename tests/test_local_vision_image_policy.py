import numpy as np

from cloudhime_workers import resolve_local_vision_image_max_width


def test_local_vision_policy_reduces_large_images_without_upscaling():
    image = np.zeros((900, 2560, 3), dtype=np.uint8)

    assert resolve_local_vision_image_max_width(image) == 1280


def test_local_vision_policy_keeps_small_text_geometry_at_native_ai_limit():
    image = np.zeros((900, 2560, 3), dtype=np.uint8)
    hints = [{"x": 20, "y": 30, "w": 240, "h": 16, "text": "tiny"}]

    assert resolve_local_vision_image_max_width(image, hints) == 1536


def test_local_vision_policy_does_not_upscale_small_images():
    image = np.zeros((600, 900, 3), dtype=np.uint8)

    assert resolve_local_vision_image_max_width(image) == 900
