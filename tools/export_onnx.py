"""Export the trained cattle checkpoint for ONNX Runtime Web."""

from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn
from torchvision import models

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_PATH = ROOT / "models" / "cattle_breed_model.pth"
OUTPUT_DIRECTORY = ROOT / "static" / "models"
MODEL_PATH = OUTPUT_DIRECTORY / "cattle_breed_model.onnx"
CLASSES_PATH = OUTPUT_DIRECTORY / "cattle_breed_classes.json"


def main() -> None:
    checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("Checkpoint must contain model weights and class labels.")

    state_dict = checkpoint.get("model_state")
    classes = checkpoint.get("classes")
    if not isinstance(state_dict, dict) or not isinstance(classes, list):
        raise ValueError("Checkpoint is missing model weights or class labels.")
    if len(classes) != 50 or not all(
        isinstance(label, str) and label for label in classes
    ):
        raise ValueError("Checkpoint must contain 50 non-empty class labels.")

    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(state_dict, assign=True)
    model.eval()

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        torch.zeros((1, 3, 224, 224), dtype=torch.float32),
        MODEL_PATH,
        input_names=["images"],
        output_names=["logits"],
        opset_version=17,
        do_constant_folding=True,
        dynamo=False,
    )

    import onnx

    exported_model = onnx.load(MODEL_PATH)
    onnx.checker.check_model(exported_model)
    CLASSES_PATH.write_text(
        json.dumps(classes, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Exported and validated {MODEL_PATH} ({MODEL_PATH.stat().st_size:,} bytes).")
    print(f"Saved {len(classes)} ordered breed labels to {CLASSES_PATH}.")


if __name__ == "__main__":
    main()
