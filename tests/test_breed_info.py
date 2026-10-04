import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import breed_info


class BreedInfoDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.dataset_path = Path(self.temp_directory.name) / "breed_information.json"
        self.practical_dataset_path = (
            Path(self.temp_directory.name) / "practical_breed_information.json"
        )
        self.dataset_patch = patch.object(breed_info, "DATASET_PATH", self.dataset_path)
        self.practical_dataset_patch = patch.object(
            breed_info,
            "PRACTICAL_INFO_DATASET_PATH",
            self.practical_dataset_path,
        )
        self.dataset_patch.start()
        self.practical_dataset_patch.start()

    def tearDown(self):
        self.practical_dataset_patch.stop()
        self.dataset_patch.stop()
        self.temp_directory.cleanup()

    def write_dataset(self, content):
        self.dataset_path.write_text(json.dumps(content), encoding="utf-8")
        self.practical_dataset_path.write_text(
            json.dumps(
                {
                    "important_note": "Values are indicative.",
                    "breeds": [
                        {
                            "model_label": "Amritmahal",
                            "scientific_name": "Bos indicus",
                            "average_adult_weight_kg": {
                                "male": {"min": 500, "max": 650},
                                "female": {"min": 350, "max": 450},
                            },
                            "typical_lifespan_years": {"min": 15, "max": 20},
                            "daily_food_intake": {
                                "maintenance_dry_matter_kg_per_day": 8,
                                "lactating_dry_matter_kg_per_day": {
                                    "min": 10,
                                    "max": 12,
                                },
                                "unit": "kg dry matter/day",
                            },
                            "milk_production_l_per_day": {
                                "typical_min": 2,
                                "typical_max": 3,
                            },
                            "primary_use": "draft",
                            "primary_use_description": "Used for draught work.",
                            "identification_features": "Grey, muscular cattle.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_loads_breed_info_case_insensitively(self):
        self.write_dataset(
            {
                "schema_version": "1.1.0",
                "breeds": {
                    "0": {
                        "name": "Amritmahal",
                        "overview": "A hardy cattle breed.",
                        "top_5_characteristics": [
                            {"title": "Adaptation", "description": "Heat tolerant."}
                        ],
                        "care_guide": {"housing": "Provide shade."},
                        "similar_breeds": ["Hallikar"],
                    }
                },
            }
        )

        result = breed_info.get_breed_info(" amritmahal ")
        self.assertEqual(
            result["overview"],
            "A hardy cattle breed.",
        )
        self.assertEqual(
            result["characteristics"],
            [{"name": "Adaptation", "details": "Heat tolerant."}],
        )
        self.assertEqual(
            result["care_guide"],
            [{"name": "Housing", "details": "Provide shade."}],
        )
        self.assertEqual(result["similar_breeds"], ["Hallikar"])
        self.assertEqual(
            next(fact for fact in result["overview_facts"] if fact["name"] == "Adult weight")[
                "details"
            ],
            "Male: 500–650 kg; female: 350–450 kg",
        )
        self.assertEqual(result["overview_note"], "Values are indicative.")

    def test_loads_supplied_dataset_file(self):
        with patch.object(
            breed_info,
            "DATASET_PATH",
            Path(breed_info.__file__).parent
            / "models"
            / "indian_cattle_breeds_api.json",
        ), patch.object(
            breed_info,
            "PRACTICAL_INFO_DATASET_PATH",
            Path(breed_info.__file__).parent
            / "models"
            / "indian_cattle_info_api.json",
        ):
            info = breed_info.get_breed_info("Amritmahal")

        self.assertIsNotNone(info)
        self.assertIn("Karnataka", info["overview"])
        self.assertEqual(len(info["characteristics"]), 5)
        self.assertEqual(len(info["care_guide"]), 6)
        self.assertIn("Hallikar", info["similar_breeds"])
        self.assertEqual(len(info["overview_facts"]), 7)
        self.assertTrue(
            any(fact["name"] == "Adult weight" for fact in info["overview_facts"])
        )

    def test_returns_none_for_a_breed_missing_from_dataset(self):
        self.write_dataset({"breeds": {}})

        self.assertIsNone(breed_info.get_breed_info("Unknown"))

    def test_rejects_invalid_dataset_json(self):
        self.dataset_path.write_text("{invalid", encoding="utf-8")

        with self.assertRaisesRegex(breed_info.BreedDatasetError, "invalid JSON"):
            breed_info.get_breed_info("Amritmahal")

    def test_rejects_incomplete_breed_entry(self):
        self.write_dataset(
            {
                "breeds": {
                    "0": {
                        "name": "Amritmahal",
                        "overview": "A hardy cattle breed.",
                        "care_guide": {"feeding": "Provide fodder."},
                        "similar_breeds": ["Hallikar"],
                    }
                }
            }
        )

        with self.assertRaisesRegex(
            breed_info.BreedDatasetError, "top_5_characteristics"
        ):
            breed_info.get_breed_info("Amritmahal")


if __name__ == "__main__":
    unittest.main()
