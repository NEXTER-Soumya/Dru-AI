"""Inference adapter for the cattle ResNet-18 checkpoint."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

MODEL_PATH = Path(__file__).resolve().parent / "models" / "cattle_breed_model.pth"
MAX_IMAGE_PIXELS = 20_000_000


class ModelError(RuntimeError):
    """Raised when the checkpoint cannot be loaded or an image cannot be inferred."""


_model: Any = None
_classes: list[str] | None = None
_torch: Any = None
_transforms: Any = None


def _load_model() -> None:
    global _model, _classes, _torch, _transforms

    if _model is not None:
        return

    try:
        import torch
        import torch.nn as nn
        from torchvision import models, transforms

        checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
        if not isinstance(checkpoint, dict):
            raise ValueError("Checkpoint must contain model weights and class labels.")

        state_dict = checkpoint.get("model_state")
        classes = checkpoint.get("classes")
        if not isinstance(state_dict, dict) or not isinstance(classes, list):
            raise ValueError("Checkpoint is missing model weights or class labels.")
        if len(classes) != 50 or not all(isinstance(name, str) for name in classes):
            raise ValueError("Checkpoint must contain the 50 training class labels.")

        model = models.resnet18(weights=None)
        model.fc = nn.Linear(model.fc.in_features, len(classes))
        model.load_state_dict(state_dict, assign=True)
        model.eval()

        _model = model
        _classes = classes
        _torch = torch
        _transforms = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    [0.485, 0.456, 0.406],
                    [0.229, 0.224, 0.225],
                ),
            ]
        )
    except Exception as exc:
        raise ModelError("Could not load the cattle breed checkpoint.") from exc


def predict_breed(image_bytes: bytes) -> dict[str, float | str]:
    _load_model()
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image resolution exceeds the supported limit.")
            image = ImageOps.exif_transpose(source).convert("RGB")
        tensor = _transforms(image).unsqueeze(0)
        with _torch.inference_mode():
            probabilities = _torch.softmax(_model(tensor), dim=1)[0]
            confidence, class_index = probabilities.max(dim=0)
        return {
            "breed": _classes[class_index.item()],
            "confidence": round(float(confidence.item()) * 100, 2),
        }
    except (UnidentifiedImageError, OSError, ValueError, IndexError) as exc:
        raise ModelError("Could not process the uploaded image.") from exc
    except Exception as exc:
        raise ModelError("Breed inference failed.") from exc
