from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CLIMATE_OPTIONS: list[dict[str, str]] = [
    {"id": "irvine", "label": "Irvine, CA", "zone": "10a", "region": "CA"},
    {"id": "santa-barbara", "label": "Santa Barbara, CA", "zone": "9b", "region": "CA"},
    {"id": "phoenix", "label": "Phoenix, AZ", "zone": "10b", "region": "Southwest"},
    {"id": "seattle", "label": "Seattle, WA", "zone": "8b", "region": "PacificNW"},
]

PLANT_LIBRARY: list[dict[str, Any]] = [
    {
        "id": "ceanothus",
        "name": "California Lilac",
        "emoji": "🪻",
        "zones": ["8b", "9b", "10a"],
        "nativeRegions": ["CA"],
        "waterUsage": "Low",
        "pollinatorValue": "High",
        "carbonSequestration": "Medium",
        "shadeCoverage": "Medium",
        "droughtResistance": "High",
    },
    {
        "id": "toyon",
        "name": "Toyon",
        "emoji": "🌿",
        "zones": ["8b", "9b", "10a"],
        "nativeRegions": ["CA"],
        "waterUsage": "Low",
        "pollinatorValue": "High",
        "carbonSequestration": "High",
        "shadeCoverage": "Medium",
        "droughtResistance": "High",
    },
    {
        "id": "manzanita",
        "name": "Manzanita",
        "emoji": "🪴",
        "zones": ["8b", "9b", "10a"],
        "nativeRegions": ["CA"],
        "waterUsage": "Low",
        "pollinatorValue": "Medium",
        "carbonSequestration": "Medium",
        "shadeCoverage": "Low",
        "droughtResistance": "High",
    },
    {
        "id": "yarrow",
        "name": "Yarrow",
        "emoji": "🌼",
        "zones": ["8b", "9b", "10a", "10b"],
        "nativeRegions": ["CA", "PacificNW"],
        "waterUsage": "Low",
        "pollinatorValue": "High",
        "carbonSequestration": "Low",
        "shadeCoverage": "Low",
        "droughtResistance": "High",
    },
    {
        "id": "milkweed",
        "name": "Narrowleaf Milkweed",
        "emoji": "🐝",
        "zones": ["9b", "10a", "10b"],
        "nativeRegions": ["CA", "Southwest"],
        "waterUsage": "Medium",
        "pollinatorValue": "High",
        "carbonSequestration": "Medium",
        "shadeCoverage": "Low",
        "droughtResistance": "Medium",
    },
    {
        "id": "lavender",
        "name": "Lavender",
        "emoji": "💜",
        "zones": ["8b", "9b", "10a", "10b"],
        "nativeRegions": ["CA", "Southwest"],
        "waterUsage": "Low",
        "pollinatorValue": "High",
        "carbonSequestration": "Medium",
        "shadeCoverage": "Low",
        "droughtResistance": "High",
    },
    {
        "id": "sage",
        "name": "White Sage",
        "emoji": "🌱",
        "zones": ["8b", "9b", "10a", "10b"],
        "nativeRegions": ["CA", "Southwest"],
        "waterUsage": "Low",
        "pollinatorValue": "High",
        "carbonSequestration": "Low",
        "shadeCoverage": "Low",
        "droughtResistance": "High",
    },
    {
        "id": "oregon-grape",
        "name": "Oregon Grape",
        "emoji": "🍃",
        "zones": ["8b", "9b"],
        "nativeRegions": ["PacificNW"],
        "waterUsage": "Medium",
        "pollinatorValue": "Medium",
        "carbonSequestration": "Medium",
        "shadeCoverage": "Medium",
        "droughtResistance": "Medium",
    },
    {
        "id": "dwarf-citrus",
        "name": "Dwarf Citrus",
        "emoji": "🍋",
        "zones": ["9b", "10a", "10b"],
        "nativeRegions": ["Southeast"],
        "waterUsage": "High",
        "pollinatorValue": "Medium",
        "carbonSequestration": "High",
        "shadeCoverage": "Medium",
        "droughtResistance": "Low",
    },
]

PLANTS_BY_ID: dict[str, dict[str, Any]] = {plant["id"]: plant for plant in PLANT_LIBRARY}

WATER_EFFICIENCY_POINTS = {"Low": 100, "Medium": 70, "High": 35}
RATING_POINTS = {"Low": 40, "Medium": 70, "High": 100}
WATER_UNITS = {"Low": 1, "Medium": 2, "High": 3}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def weighted_average(values: list[float], weights: list[float]) -> float:
    if not values or not weights:
        return 0.0
    total_weight = sum(weights)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def get_climate_profile(climate_id: str | None) -> dict[str, str]:
    if not climate_id:
        return CLIMATE_OPTIONS[0]
    return next((item for item in CLIMATE_OPTIONS if item["id"] == climate_id), CLIMATE_OPTIONS[0])


def recommend_plants(climate_profile: dict[str, str]) -> list[dict[str, Any]]:
    region = climate_profile["region"]
    zone = climate_profile["zone"]

    native_by_zone = [
        plant
        for plant in PLANT_LIBRARY
        if region in plant["nativeRegions"] and zone in plant["zones"]
    ]
    adaptive_by_zone = [
        plant
        for plant in PLANT_LIBRARY
        if region not in plant["nativeRegions"] and zone in plant["zones"]
    ]
    native_fallback = [
        plant
        for plant in PLANT_LIBRARY
        if region in plant["nativeRegions"] and zone not in plant["zones"]
    ]

    ordered = native_by_zone + adaptive_by_zone + native_fallback
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for plant in ordered:
        plant_id = plant["id"]
        if plant_id in seen:
            continue
        seen.add(plant_id)
        deduped.append(plant)

    return deduped[:8]


def compute_metrics(
    climate_profile: dict[str, str], placed_plants_payload: list[dict[str, Any]]
) -> dict[str, int]:
    region = climate_profile["region"]
    resolved_entries: list[tuple[dict[str, Any], float]] = []

    for payload in placed_plants_payload:
        plant_id = payload.get("plantId") or payload.get("plant_id")
        if not isinstance(plant_id, str):
            continue
        plant = PLANTS_BY_ID.get(plant_id)
        if plant is None:
            continue
        raw_size = payload.get("size", 56)
        size = float(raw_size) if isinstance(raw_size, (int, float)) else 56.0
        normalized_weight = clamp(size / 56.0, 0.6, 2.4)
        resolved_entries.append((plant, normalized_weight))

    if not resolved_entries:
        return {
            "sustainabilityScore": 0,
            "waterEfficiency": 0,
            "pollinatorSupport": 0,
            "nativePercent": 0,
            "droughtResistance": 0,
            "biodiversity": 0,
            "carbonImpact": 0,
            "weeklyWaterDemand": 0,
        }

    plants = [plant for plant, _weight in resolved_entries]
    weights = [weight for _plant, weight in resolved_entries]
    total_weight = sum(weights)

    water_efficiency = round(
        weighted_average([WATER_EFFICIENCY_POINTS[plant["waterUsage"]] for plant in plants], weights)
    )
    pollinator_support = round(
        weighted_average([RATING_POINTS[plant["pollinatorValue"]] for plant in plants], weights)
    )
    drought_resistance = round(
        weighted_average([RATING_POINTS[plant["droughtResistance"]] for plant in plants], weights)
    )
    carbon_impact = round(
        weighted_average([RATING_POINTS[plant["carbonSequestration"]] for plant in plants], weights)
    )

    native_weight = sum(
        weight for plant, weight in resolved_entries if region in plant["nativeRegions"]
    )
    native_percent = round((native_weight / total_weight) * 100) if total_weight else 0

    unique_species = len({plant["id"] for plant in plants})
    biodiversity = round(
        clamp((unique_species / len(plants)) * 70 + min(unique_species, 6) * 5 + 25, 0, 100)
    )
    weekly_water_demand = round(
        sum(WATER_UNITS[plant["waterUsage"]] * weight for plant, weight in resolved_entries)
    )

    sustainability_score = round(
        native_percent * 0.28
        + water_efficiency * 0.24
        + pollinator_support * 0.16
        + drought_resistance * 0.14
        + biodiversity * 0.10
        + carbon_impact * 0.08
    )

    return {
        "sustainabilityScore": sustainability_score,
        "waterEfficiency": water_efficiency,
        "pollinatorSupport": pollinator_support,
        "nativePercent": native_percent,
        "droughtResistance": drought_resistance,
        "biodiversity": biodiversity,
        "carbonImpact": carbon_impact,
        "weeklyWaterDemand": weekly_water_demand,
    }


@app.get("/api/health")
def health_check() -> Any:
    return jsonify({"status": "ok"})


@app.get("/api/config")
def config() -> Any:
    return jsonify(
        {
            "climateOptions": CLIMATE_OPTIONS,
            "plantLibrary": PLANT_LIBRARY,
            "constraints": {"minGardenDimension": 6, "maxGardenDimension": 24},
        }
    )


@app.get("/api/recommendations")
def recommendations() -> Any:
    climate_id = request.args.get("climateId") or request.args.get("climate_id")
    climate_profile = get_climate_profile(climate_id)
    return jsonify({"climate": climate_profile, "plants": recommend_plants(climate_profile)})


@app.post("/api/score")
def score() -> Any:
    payload = request.get_json(silent=True) or {}
    climate_id = payload.get("climateId") or payload.get("climate_id")
    placed_plants_payload = payload.get("placedPlants") or payload.get("placed_plants") or []

    if not isinstance(placed_plants_payload, list):
        return jsonify({"error": "placedPlants must be a list"}), 400

    climate_profile = get_climate_profile(climate_id)
    metrics = compute_metrics(climate_profile, placed_plants_payload)
    return jsonify({"climate": climate_profile, "metrics": metrics})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=True)
