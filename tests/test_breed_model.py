import unittest
from pathlib import Path

from breed_model import predict_breed


class BreedModelTests(unittest.TestCase):
    def test_checkpoint_returns_a_breed_and_top_class_confidence(self):
        image_path = Path(__file__).resolve().parents[1] / "static" / "mockups" / "animals_1.png"
        prediction = predict_breed(image_path.read_bytes())

        self.assertIsInstance(prediction["breed"], str)
        self.assertTrue(prediction["breed"])
        self.assertGreaterEqual(prediction["confidence"], 0)
        self.assertLessEqual(prediction["confidence"], 100)


if __name__ == "__main__":
    unittest.main()
