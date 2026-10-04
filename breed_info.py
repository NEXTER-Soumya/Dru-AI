"""Read cattle-breed reference information from the local JSON dataset."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any


DATASET_PATH = (
    Path(__file__).resolve().parent / "models" / "indian_cattle_breeds_api.json"
)
PRACTICAL_INFO_DATASET_PATH = (
    Path(__file__).resolve().parent / "models" / "indian_cattle_info_api.json"
)


class BreedDatasetError(RuntimeError):
    """Raised when the local breed information dataset is missing or invalid."""


def _normalize_breed_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).replace("_", " ")
    return " ".join(normalized.split()).casefold()


def _validate_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BreedDatasetError(f"Dataset field '{field}' must be a non-empty string.")
    return value.strip()


def _number(value: Any, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BreedDatasetError(f"Dataset field '{field}' must be numeric.")
    return f"{value:g}"


def _format_range(value: Any, field: str, unit: str) -> str:
    if not isinstance(value, dict):
        raise BreedDatasetError(f"Dataset field '{field}' must be an object.")
    minimum = _number(value.get("min"), f"{field}.min")
    maximum = _number(value.get("max"), f"{field}.max")
    return f"{minimum}–{maximum} {unit}"


def _overview_facts(entry: Any, breed: str) -> list[dict[str, str]]:
    if not isinstance(entry, dict):
        raise BreedDatasetError(
            f"Practical information entry for '{breed}' must be an object."
        )

    weight = entry.get("average_adult_weight_kg")
    if not isinstance(weight, dict):
        raise BreedDatasetError(
            f"Dataset field 'average_adult_weight_kg' for '{breed}' must be an object."
        )
    lifespan = _format_range(
        entry.get("typical_lifespan_years"),
        "typical_lifespan_years",
        "years",
    )
    male_weight = _format_range(weight.get("male"), "average_adult_weight_kg.male", "kg")
    female_weight = _format_range(
        weight.get("female"), "average_adult_weight_kg.female", "kg"
    )

    food = entry.get("daily_food_intake")
    if not isinstance(food, dict):
        raise BreedDatasetError(
            f"Dataset field 'daily_food_intake' for '{breed}' must be an object."
        )
    food_unit = _validate_text(food.get("unit"), "daily_food_intake.unit")
    maintenance = _number(
        food.get("maintenance_dry_matter_kg_per_day"),
        "daily_food_intake.maintenance_dry_matter_kg_per_day",
    )
    lactating = _format_range(
        food.get("lactating_dry_matter_kg_per_day"),
        "daily_food_intake.lactating_dry_matter_kg_per_day",
        food_unit,
    )

    milk = entry.get("milk_production_l_per_day")
    if not isinstance(milk, dict):
        raise BreedDatasetError(
            f"Dataset field 'milk_production_l_per_day' for '{breed}' must be an object."
        )
    milk_min = _number(milk.get("typical_min"), "milk_production_l_per_day.typical_min")
    milk_max = _number(milk.get("typical_max"), "milk_production_l_per_day.typical_max")

    scientific_name = _validate_text(entry.get("scientific_name"), "scientific_name")
    primary_use = _validate_text(entry.get("primary_use"), "primary_use")
    primary_use_description = _validate_text(
        entry.get("primary_use_description"), "primary_use_description"
    )
    identification_features = _validate_text(
        entry.get("identification_features"), "identification_features"
    )

    return [
        {"name": "Scientific name", "details": scientific_name},
        {
            "name": "Adult weight",
            "details": f"Male: {male_weight}; female: {female_weight}",
        },
        {"name": "Typical lifespan", "details": lifespan},
        {"name": "Milk production", "details": f"{milk_min}–{milk_max} litres/day"},
        {
            "name": "Daily food intake",
            "details": (
                f"Maintenance: {maintenance} {food_unit}; "
                f"lactating: {lactating}"
            ),
        },
        {
            "name": f"Primary use · {primary_use.replace('_', ' ').title()}",
            "details": primary_use_description,
        },
        {"name": "Identification features", "details": identification_features},
    ]


def _validate_items(value: Any, field: str, detail_key: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise BreedDatasetError(f"Dataset field '{field}' must be a non-empty list.")

    items = []
    for item in value:
        if not isinstance(item, dict):
            raise BreedDatasetError(f"Each '{field}' entry must be an object.")
        items.append(
            {
                "name": _validate_text(item.get("name"), f"{field}.name"),
                detail_key: _validate_text(item.get(detail_key), f"{field}.{detail_key}"),
            }
        )
    return items


def _validate_entry(entry: Any, breed: str) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise BreedDatasetError(f"Dataset entry for '{breed}' must be an object.")
    care_guide = entry.get("care_guide")
    if not isinstance(care_guide, dict) or not care_guide:
        raise BreedDatasetError(
            f"Dataset field 'care_guide' for '{breed}' must be a non-empty object."
        )
    if not all(isinstance(value, str) and value.strip() for value in care_guide.values()):
        raise BreedDatasetError(
            f"Dataset field 'care_guide' for '{breed}' must contain text values."
        )
    similar_breeds = entry.get("similar_breeds")
    if not isinstance(similar_breeds, list) or not similar_breeds:
        raise BreedDatasetError(
            f"Dataset field 'similar_breeds' for '{breed}' must be a non-empty list."
        )
    raw_characteristics = entry.get("top_5_characteristics")
    if not isinstance(raw_characteristics, list):
        raise BreedDatasetError(
            f"Dataset field 'top_5_characteristics' for '{breed}' must be a list."
        )

    characteristics = _validate_items(
        [
            {"name": item.get("title"), "details": item.get("description")}
            if isinstance(item, dict)
            else item
            for item in raw_characteristics
        ],
        "top_5_characteristics",
        "details",
    )

    care_items = [
        {
            "name": category.replace("_", " ").replace("/", " / ").title(),
            "details": details,
        }
        for category, details in care_guide.items()
    ]

    return {
        "overview": _validate_text(entry.get("overview"), "overview"),
        "characteristics": characteristics,
        "care_guide": [
            {
                "name": _validate_text(item.get("name"), "care_guide.name"),
                "details": _validate_text(item.get("details"), "care_guide.details"),
            }
            for item in care_items
        ],
        "similar_breeds": [
            _validate_text(name, "similar_breeds item") for name in similar_breeds
        ],
    }


def get_breed_info(breed: str) -> dict[str, Any] | None:
    try:
        with DATASET_PATH.open(encoding="utf-8") as dataset_file:
            dataset = json.load(dataset_file)
    except FileNotFoundError as exc:
        raise BreedDatasetError(
            f"Breed dataset not found at '{DATASET_PATH}'."
        ) from exc
    except json.JSONDecodeError as exc:
        raise BreedDatasetError(
            f"Breed dataset contains invalid JSON at line {exc.lineno}."
        ) from exc
    except OSError as exc:
        raise BreedDatasetError("Breed dataset could not be read.") from exc

    if not isinstance(dataset, dict) or not isinstance(dataset.get("breeds"), dict):
        raise BreedDatasetError(
            "The breed dataset must contain a 'breeds' object."
        )

    try:
        with PRACTICAL_INFO_DATASET_PATH.open(encoding="utf-8") as dataset_file:
            practical_dataset = json.load(dataset_file)
    except FileNotFoundError as exc:
        raise BreedDatasetError(
            f"Practical breed dataset not found at '{PRACTICAL_INFO_DATASET_PATH}'."
        ) from exc
    except json.JSONDecodeError as exc:
        raise BreedDatasetError(
            f"Practical breed dataset contains invalid JSON at line {exc.lineno}."
        ) from exc
    except OSError as exc:
        raise BreedDatasetError("Practical breed dataset could not be read.") from exc

    if (
        not isinstance(practical_dataset, dict)
        or not isinstance(practical_dataset.get("breeds"), list)
    ):
        raise BreedDatasetError(
            "The practical breed dataset must contain a 'breeds' list."
        )

    target_name = _normalize_breed_name(breed)
    practical_entry = None
    for entry in practical_dataset["breeds"]:
        if not isinstance(entry, dict):
            raise BreedDatasetError(
                "Each practical breed dataset entry must be an object."
            )
        dataset_breed = entry.get("model_label")
        if not isinstance(dataset_breed, str) or not dataset_breed.strip():
            raise BreedDatasetError(
                "Each practical breed dataset entry must have a model_label."
            )
        if _normalize_breed_name(dataset_breed) == target_name:
            practical_entry = entry
            break

    for entry in dataset["breeds"].values():
        if not isinstance(entry, dict):
            raise BreedDatasetError("Each breed dataset entry must be an object.")
        dataset_breed = entry.get("name")
        if not isinstance(dataset_breed, str) or not dataset_breed.strip():
            raise BreedDatasetError("Each breed dataset entry must have a name.")
        if _normalize_breed_name(dataset_breed) == target_name:
            info = _validate_entry(entry, dataset_breed)
            if practical_entry is None:
                raise BreedDatasetError(
                    f"Practical information for '{dataset_breed}' was not found."
                )
            info["overview_facts"] = _overview_facts(practical_entry, dataset_breed)
            info["overview_note"] = _validate_text(
                practical_dataset.get("important_note"),
                "important_note",
            )
            return info
    return None
