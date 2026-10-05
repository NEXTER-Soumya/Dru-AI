import json
import unittest
from pathlib import Path


class BrowserModelAssetTests(unittest.TestCase):
    def test_browser_model_and_ordered_breed_labels_are_deployed(self):
        static_directory = Path(__file__).resolve().parents[1] / "static"
        model_path = static_directory / "models" / "cattle_breed_model.onnx"
        classes_path = static_directory / "models" / "cattle_breed_classes.json"

        self.assertGreater(model_path.stat().st_size, 1_000_000)
        classes = json.loads(classes_path.read_text(encoding="utf-8"))
        self.assertEqual(len(classes), 50)
        self.assertTrue(all(isinstance(label, str) and label for label in classes))


if __name__ == "__main__":
    unittest.main()
