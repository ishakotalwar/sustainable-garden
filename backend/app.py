from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        os.environ.setdefault(key, value)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_env_file(PROJECT_ROOT / ".env")

FLORA_API_BASE_URL = os.getenv("FLORA_API_BASE_URL", "https://api.floraapi.com").rstrip("/")
FLORA_API_KEY = os.getenv("FLORA_API_KEY", "").strip()

STATE_TO_REGION: dict[str, str] = {
    "CA": "CA",
    "AZ": "Southwest",
    "NM": "Southwest",
    "NV": "Southwest",
    "UT": "Southwest",
    "CO": "Southwest",
    "WA": "PacificNW",
    "OR": "PacificNW",
    "ID": "PacificNW",
    "AK": "PacificNW",
    "HI": "PacificNW",
}

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
DYNAMIC_CLIMATE_PROFILES: dict[str, dict[str, str]] = {}

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


def flora_enabled() -> bool:
    return bool(FLORA_API_KEY)


def flora_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {FLORA_API_KEY}"}


def flora_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not flora_enabled():
        raise RuntimeError("FLORA_API_KEY is not set.")

    response = requests.get(
        f"{FLORA_API_BASE_URL}{path}",
        params=params,
        headers=flora_headers(),
        timeout=12,
    )
    response.raise_for_status()
    return response.json()


def normalize_zip_code(raw_zip: str | None) -> str | None:
    if not raw_zip:
        return None
    digits = "".join(ch for ch in raw_zip if ch.isdigit())
    if len(digits) < 5:
        return None
    return digits[:5]


def region_from_state(state_code: str | None) -> str:
    if not state_code:
        return "Southeast"
    return STATE_TO_REGION.get(state_code.upper(), "Southeast")


def fallback_zone_for_region(region: str) -> str:
    if region == "CA":
        return "10a"
    if region == "PacificNW":
        return "8b"
    if region == "Southwest":
        return "9b"
    return "9a"


def normalize_rating(value: Any, default: str = "Medium") -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    if any(token in normalized for token in ("low", "least", "minimal", "drought", "dry")):
        return "Low"
    if any(token in normalized for token in ("high", "heavy", "major", "abundant", "strong")):
        return "High"
    if any(token in normalized for token in ("medium", "moderate", "average")):
        return "Medium"
    return default


def extract_species_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("species", "results", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    for value in payload.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
    return []


def extract_state_code(payload: Any) -> str | None:
    if isinstance(payload, dict):
        prioritized_keys = [
            "state",
            "state_code",
            "stateCode",
            "us_state",
            "usState",
            "abbr",
            "abbreviation",
        ]
        for key in prioritized_keys:
            value = payload.get(key)
            if isinstance(value, str) and re.fullmatch(r"[A-Za-z]{2}", value.strip()):
                return value.strip().upper()
        for value in payload.values():
            result = extract_state_code(value)
            if result:
                return result
    if isinstance(payload, list):
        for item in payload:
            result = extract_state_code(item)
            if result:
                return result
    return None


def extract_zone_hint(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("hardiness_zone", "hardinessZone", "usda_zone", "zone", "hardiness"):
            value = payload.get(key)
            if isinstance(value, str):
                match = re.search(r"\d{1,2}[abAB]?", value)
                if match:
                    return match.group(0).lower()
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        match = re.search(r"\d{1,2}[abAB]?", item)
                        if match:
                            return match.group(0).lower()
        for value in payload.values():
            result = extract_zone_hint(value)
            if result:
                return result
    if isinstance(payload, list):
        for item in payload:
            result = extract_zone_hint(item)
            if result:
                return result
    return None


def flora_emoji_for_species(species: dict[str, Any]) -> str:
    habit = str(
        species.get("habit")
        or species.get("plant_habit")
        or species.get("growth_habit")
        or species.get("growth_form")
        or ""
    ).lower()
    if "tree" in habit:
        return "🌳"
    if "shrub" in habit or "bush" in habit:
        return "🌿"
    if "grass" in habit or "sedge" in habit:
        return "🌾"
    if "vine" in habit:
        return "🍃"
    if "flower" in habit or "forb" in habit:
        return "🌸"
    return "🪴"


def parse_zones(species: dict[str, Any], zone_hint: str) -> list[str]:
    zone_candidates: list[str] = []
    for key in ("hardiness_zones", "hardiness_zone", "usda_hardiness_zones", "zones"):
        value = species.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    zone_candidates.extend(re.findall(r"\d{1,2}[abAB]?", item))
        elif isinstance(value, str):
            zone_candidates.extend(re.findall(r"\d{1,2}[abAB]?", value))
    cleaned = [zone.lower() for zone in zone_candidates if zone]
    if cleaned:
        return sorted(list(dict.fromkeys(cleaned)))
    return [zone_hint]


def flora_species_to_plant(
    species: dict[str, Any], state_code: str, zone_hint: str, position: int
) -> dict[str, Any]:
    plant_id_source = (
        species.get("usda_symbol")
        or species.get("symbol")
        or species.get("identifier")
        or species.get("id")
        or species.get("species_id")
        or f"{state_code}-flora-{position}"
    )
    plant_id = str(plant_id_source).strip().lower().replace(" ", "-")
    scientific_name = str(species.get("scientific_name") or "").strip()
    common_name = str(species.get("common_name") or "").strip()
    display_name = common_name or scientific_name or f"Plant {position + 1}"

    nativity_text = str(
        species.get("nativity_status")
        or species.get("native_status")
        or species.get("status")
        or "native"
    ).lower()
    is_native = "introduced" not in nativity_text and "non-native" not in nativity_text
    region = region_from_state(state_code)

    pollinator_source = (
        species.get("pollinator_value")
        or species.get("pollinator_support")
        or species.get("wildlife_value")
        or species.get("wildlife_support")
        or "Medium"
    )
    carbon_source = (
        species.get("carbon_sequestration")
        or species.get("carbon_value")
        or species.get("biomass_value")
        or "Medium"
    )
    water_source = species.get("water_usage") or species.get("water_needs") or "Medium"
    shade_source = species.get("shade_tolerance") or species.get("shade_coverage") or "Medium"
    drought_source = species.get("drought_tolerance") or species.get("drought_resistance") or "Medium"

    return {
        "id": plant_id,
        "name": display_name,
        "emoji": flora_emoji_for_species(species),
        "zones": parse_zones(species, zone_hint),
        "nativeRegions": [region] if is_native else [],
        "waterUsage": normalize_rating(water_source, default="Medium"),
        "pollinatorValue": normalize_rating(pollinator_source, default="Medium"),
        "carbonSequestration": normalize_rating(carbon_source, default="Medium"),
        "shadeCoverage": normalize_rating(shade_source, default="Medium"),
        "droughtResistance": normalize_rating(drought_source, default="Medium"),
    }


def register_runtime_plants(plants: list[dict[str, Any]]) -> None:
    for plant in plants:
        plant_id = plant.get("id")
        if not isinstance(plant_id, str) or not plant_id:
            continue
        PLANTS_BY_ID[plant_id] = plant
        if not any(existing.get("id") == plant_id for existing in PLANT_LIBRARY):
            PLANT_LIBRARY.append(plant)


def flora_recommendations_for_zip(zip_code: str) -> tuple[dict[str, str], list[dict[str, Any]], str]:
    climate_payload = flora_get(f"/v1/climate/zipcode/{zip_code}")
    state_code = extract_state_code(climate_payload) or "CA"
    region = region_from_state(state_code)
    zone_hint = extract_zone_hint(climate_payload) or fallback_zone_for_region(region)

    search_payload = flora_get(
        "/v1/search",
        params={"state": state_code, "native_only": True, "limit": 24},
    )
    species_entries = extract_species_list(search_payload)
    if not species_entries:
        region_payload = flora_get(f"/v1/regions/{state_code}/native", params={"limit": 24})
        species_entries = extract_species_list(region_payload)

    flora_plants: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, species in enumerate(species_entries):
        mapped_plant = flora_species_to_plant(species, state_code=state_code, zone_hint=zone_hint, position=position)
        plant_id = mapped_plant["id"]
        if plant_id in seen_ids:
            continue
        seen_ids.add(plant_id)
        flora_plants.append(mapped_plant)
        if len(flora_plants) >= 12:
            break

    climate_profile = {
        "id": f"zip-{zip_code}",
        "label": f"ZIP {zip_code} ({state_code})",
        "zone": zone_hint,
        "region": region,
    }
    return climate_profile, flora_plants, state_code


def get_climate_profile(climate_id: str | None) -> dict[str, str]:
    if not climate_id:
        return CLIMATE_OPTIONS[0]
    if climate_id in DYNAMIC_CLIMATE_PROFILES:
        return DYNAMIC_CLIMATE_PROFILES[climate_id]
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
            "integrations": {
                "flora": {
                    "enabled": flora_enabled(),
                    "baseUrl": FLORA_API_BASE_URL,
                }
            },
        }
    )


@app.get("/api/recommendations")
def recommendations() -> Any:
    climate_id = request.args.get("climateId") or request.args.get("climate_id")
    zip_code = normalize_zip_code(request.args.get("zipCode") or request.args.get("zip_code"))
    if zip_code:
        if not flora_enabled():
            return (
                jsonify(
                    {
                        "error": "FLORA_API_KEY not set on server.",
                        "zipCode": zip_code,
                        "floraEnabled": False,
                    }
                ),
                503,
            )
        try:
            climate_profile, flora_plants, state_code = flora_recommendations_for_zip(zip_code)
        except requests.RequestException as exc:
            return (
                jsonify(
                    {
                        "error": "Flora API request failed.",
                        "detail": str(exc),
                        "zipCode": zip_code,
                        "floraEnabled": True,
                    }
                ),
                502,
            )

        DYNAMIC_CLIMATE_PROFILES[climate_profile["id"]] = climate_profile
        register_runtime_plants(flora_plants)
        return jsonify(
            {
                "climate": climate_profile,
                "plants": flora_plants,
                "zipCode": zip_code,
                "state": state_code,
                "floraEnabled": True,
                "source": "flora",
            }
        )

    climate_profile = get_climate_profile(climate_id)
    return jsonify({"climate": climate_profile, "plants": recommend_plants(climate_profile), "source": "local"})


@app.get("/api/recommendations/zipcode")
def recommendations_by_zip_code() -> Any:
    zip_code = normalize_zip_code(request.args.get("zipCode") or request.args.get("zip_code"))
    if not zip_code:
        return jsonify({"error": "A valid 5-digit zipCode is required."}), 400

    if not flora_enabled():
        return (
            jsonify(
                {
                    "error": "FLORA_API_KEY not configured on backend.",
                    "zipCode": zip_code,
                    "floraEnabled": False,
                }
            ),
            503,
        )

    try:
        climate_profile, flora_plants, state_code = flora_recommendations_for_zip(zip_code)
    except requests.RequestException as exc:
        return (
            jsonify(
                {
                    "error": "Flora API request failed.",
                    "detail": str(exc),
                    "zipCode": zip_code,
                    "floraEnabled": True,
                }
            ),
            502,
        )

    DYNAMIC_CLIMATE_PROFILES[climate_profile["id"]] = climate_profile
    register_runtime_plants(flora_plants)
    return jsonify(
        {
            "climate": climate_profile,
            "plants": flora_plants,
            "zipCode": zip_code,
            "state": state_code,
            "floraEnabled": True,
            "source": "flora",
        }
    )


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
