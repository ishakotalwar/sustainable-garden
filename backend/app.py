from __future__ import annotations

import os
import random
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

DEFAULT_CLIMATE_PROFILE: dict[str, str] = {
    "id": "local",
    "label": "Local",
    "zone": "unknown",
    "region": "generic",
}

CLIMATE_OPTIONS: list[dict[str, str]] = []

PLANT_LIBRARY: list[dict[str, Any]] = []

PLANTS_BY_ID: dict[str, dict[str, Any]] = {plant["id"]: plant for plant in PLANT_LIBRARY}
DYNAMIC_CLIMATE_PROFILES: dict[str, dict[str, str]] = {}

WATER_EFFICIENCY_POINTS = {"Low": 100, "Medium": 70, "High": 35}
RATING_POINTS = {"Low": 40, "Medium": 70, "High": 100}
WATER_UNITS = {"Low": 1, "Medium": 2, "High": 3}

PLANT_TYPE_OPTIONS: dict[str, dict[str, Any]] = {
    "flower": {
        "label": "Flower",
        "flora_habit": "forb",
        "keywords": ("flower", "forb", "wildflower", "blossom"),
    },
    "fruit": {
        "label": "Fruit",
        "flora_habit": None,
        "keywords": ("fruit", "berry", "citrus", "grape", "apple", "fig", "plum", "peach"),
    },
    "bush": {
        "label": "Bush",
        "flora_habit": "shrub",
        "keywords": ("shrub", "bush"),
    },
    "tree": {
        "label": "Tree",
        "flora_habit": "tree",
        "keywords": ("tree", "oak", "pine", "maple"),
    },
    "vine": {
        "label": "Vine",
        "flora_habit": "vine",
        "keywords": ("vine", "climber", "creeper"),
    },
    "grass": {
        "label": "Grass",
        "flora_habit": "grass",
        "keywords": ("grass", "sedge", "rush"),
    },
    "succulent": {
        "label": "Succulent",
        "flora_habit": "succulent",
        "keywords": ("succulent", "cactus", "agave", "aloe"),
    },
}


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


def normalize_plant_type(raw_plant_type: str | None) -> str | None:
    if not raw_plant_type:
        return None
    normalized = raw_plant_type.strip().lower().replace(" ", "-")
    if normalized in ("any", "all", "none"):
        return None
    if normalized in PLANT_TYPE_OPTIONS:
        return normalized
    aliases = {
        "flowers": "flower",
        "flowering": "flower",
        "fruits": "fruit",
        "berry": "fruit",
        "berries": "fruit",
        "shrub": "bush",
        "shrubs": "bush",
        "bushes": "bush",
        "trees": "tree",
        "vines": "vine",
        "grasses": "grass",
        "succulents": "succulent",
    }
    return aliases.get(normalized)


def normalize_plant_query(raw_plant_query: str | None) -> str | None:
    if not raw_plant_query:
        return None
    normalized = " ".join(raw_plant_query.strip().split())
    if not normalized:
        return None
    return normalized[:80]


def fetch_species_entries_from_candidates(
    candidates: list[tuple[str, dict[str, Any]]], strategy: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    attempted: list[dict[str, Any]] = []
    successful_calls = 0
    last_error: Exception | None = None

    for path, params in candidates:
        try:
            payload = flora_get(path, params=params)
            species_entries = extract_species_list(payload)
            successful_calls += 1
            attempted.append(
                {
                    "path": path,
                    "params": params,
                    "resultCount": len(species_entries),
                }
            )
            for species in species_entries:
                signature = str(
                    species.get("id")
                    or species.get("species_id")
                    or species.get("identifier")
                    or species.get("usda_symbol")
                    or species.get("scientific_name")
                    or species.get("common_name")
                    or ""
                ).strip()
                if not signature:
                    continue
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                collected.append(species)
                if len(collected) >= 150:
                    break
        except requests.RequestException as exc:
            last_error = exc
            attempted.append(
                {
                    "path": path,
                    "params": params,
                    "error": str(exc),
                }
            )
            continue

    if not collected and last_error is not None and successful_calls == 0:
        raise last_error

    metadata = {
        "strategy": strategy,
        "attemptedQueries": attempted,
        "successfulCalls": successful_calls,
        "combinedSpeciesCount": len(collected),
    }
    return collected, metadata


def flora_type_search_candidates(state_code: str, plant_type: str | None) -> list[tuple[str, dict[str, Any]]]:
    base_params = {"state": state_code, "native_only": True, "limit": 80}
    if not plant_type:
        return [("/v1/search", base_params)]

    if plant_type == "fruit":
        return [
            ("/v1/search/edible", {**base_params, "edible_part": "fruit"}),
            ("/v1/search", {**base_params, "q": "fruit"}),
            ("/v1/search", {**base_params, "q": "berry"}),
            ("/v1/search", {**base_params, "q": "orchard"}),
        ]

    type_terms = {
        "flower": ("forb", "flower"),
        "bush": ("shrub", "bush"),
        "tree": ("tree", "tree"),
        "vine": ("vine", "vine"),
        "grass": ("grass", "grass"),
        "succulent": ("succulent", "succulent"),
    }
    habit_value, query_term = type_terms.get(plant_type, (plant_type, plant_type))
    return [
        ("/v1/search", {**base_params, "plant_habit": habit_value}),
        ("/v1/search", {**base_params, "habit": habit_value}),
        ("/v1/search", {**base_params, "q": query_term}),
    ]


def fetch_species_entries_for_type(
    state_code: str, plant_type: str | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = flora_type_search_candidates(state_code, plant_type)
    strategy = "typed" if plant_type else "default"
    return fetch_species_entries_from_candidates(candidates, strategy)


def flora_query_search_candidates(
    state_code: str, plant_query: str, plant_type: str | None
) -> list[tuple[str, dict[str, Any]]]:
    base = {"q": plant_query, "limit": 80}
    option = PLANT_TYPE_OPTIONS.get(plant_type) if plant_type else None
    flora_habit = option.get("flora_habit") if option else None

    staged_params: list[dict[str, Any]] = [
        {**base, "state": state_code, "native_only": True},
        {**base, "state": state_code},
        {**base},
    ]

    candidates: list[tuple[str, dict[str, Any]]] = []
    seen_param_keys: set[tuple[tuple[str, str], ...]] = set()

    for params in staged_params:
        variants = [params]
        if isinstance(flora_habit, str) and flora_habit:
            variants = [
                {**params, "plant_habit": flora_habit},
                {**params, "habit": flora_habit},
                params,
            ]
        for variant in variants:
            dedupe_key = tuple(sorted((key, str(value)) for key, value in variant.items()))
            if dedupe_key in seen_param_keys:
                continue
            seen_param_keys.add(dedupe_key)
            candidates.append(("/v1/search", variant))
    return candidates


def fetch_species_entries_for_query(
    state_code: str, plant_query: str, plant_type: str | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = flora_query_search_candidates(state_code, plant_query, plant_type)
    collected, metadata = fetch_species_entries_from_candidates(candidates, "query")
    metadata["plantQuery"] = plant_query
    return collected, metadata


def species_text_blob(species: dict[str, Any]) -> str:
    fields: list[str] = []
    for key in (
        "common_name",
        "scientific_name",
        "description",
        "habit",
        "plant_habit",
        "growth_habit",
        "growth_form",
        "edible_parts",
    ):
        value = species.get(key)
        if isinstance(value, str):
            fields.append(value)
        elif isinstance(value, list):
            fields.extend(str(item) for item in value if item is not None)
    return " ".join(fields).lower()


def species_habit_text(species: dict[str, Any]) -> str:
    return str(
        species.get("habit")
        or species.get("plant_habit")
        or species.get("growth_habit")
        or species.get("growth_form")
        or ""
    ).lower()


def species_strict_match(species: dict[str, Any], plant_type: str) -> bool:
    option = PLANT_TYPE_OPTIONS.get(plant_type)
    if not option:
        return True

    keywords: tuple[str, ...] = option.get("keywords", ())
    flora_habit = option.get("flora_habit")
    habit_text = species_habit_text(species)
    text_blob = species_text_blob(species)

    if plant_type == "fruit":
        edible_parts = species.get("edible_parts")
        if isinstance(edible_parts, list) and any(
            any(token in str(part).lower() for token in ("fruit", "berry", "nut"))
            for part in edible_parts
        ):
            return True
        return any(keyword in text_blob for keyword in keywords)

    if plant_type == "flower":
        if species.get("flower_color") or species.get("flowerColor") or species.get("bloom_time"):
            return True

    if isinstance(flora_habit, str) and flora_habit and flora_habit in habit_text:
        return True
    return any(keyword in habit_text for keyword in keywords)


def species_match_score(species: dict[str, Any], plant_type: str) -> int:
    option = PLANT_TYPE_OPTIONS.get(plant_type)
    if not option:
        return 1

    keywords: tuple[str, ...] = option.get("keywords", ())
    flora_habit = option.get("flora_habit")
    habit_text = species_habit_text(species)
    text_blob = species_text_blob(species)

    score = 0
    if species_strict_match(species, plant_type):
        score += 6
    if isinstance(flora_habit, str) and flora_habit and flora_habit in habit_text:
        score += 5
    if any(keyword in habit_text for keyword in keywords):
        score += 4
    if any(keyword in text_blob for keyword in keywords):
        score += 2

    # Additional weaker signals by category.
    if plant_type == "flower":
        if species.get("flower_color") or species.get("flowerColor") or species.get("bloom_time"):
            score += 1
    if plant_type == "fruit":
        edible_parts = species.get("edible_parts")
        if isinstance(edible_parts, list) and any("fruit" in str(part).lower() for part in edible_parts):
            score += 3

    return score


def prioritize_species_by_plant_type(
    species_entries: list[dict[str, Any]], plant_type: str | None
) -> tuple[list[dict[str, Any]], int, bool]:
    if not plant_type:
        return species_entries, len(species_entries), False

    scored = [
        (species, species_match_score(species, plant_type), index)
        for index, species in enumerate(species_entries)
    ]
    strong_matches = [item for item in scored if species_strict_match(item[0], plant_type)]
    if strong_matches:
        strong_matches.sort(key=lambda item: (-item[1], item[2]))
        return [item[0] for item in strong_matches], len(strong_matches), False

    weak_matches = [item for item in scored if item[1] > 0]
    if weak_matches:
        weak_matches.sort(key=lambda item: (-item[1], item[2]))
        return [item[0] for item in weak_matches], 0, True

    # If we cannot infer type at all from metadata/text, return no results instead of
    # silently returning unrelated plants.
    return [], 0, True


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
        "nativeRegions": ["native"] if is_native else [],
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


def flora_recommendations_for_zip(
    zip_code: str, plant_type: str | None = None, plant_query: str | None = None
) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, Any]]:
    climate_payload = flora_get(f"/v1/climate/zipcode/{zip_code}")
    state_code = extract_state_code(climate_payload) or "CA"
    zone_hint = extract_zone_hint(climate_payload) or "unknown"
    normalized_plant_type = normalize_plant_type(plant_type)
    normalized_plant_query = normalize_plant_query(plant_query)

    if normalized_plant_query:
        species_entries, query_metadata = fetch_species_entries_for_query(
            state_code, normalized_plant_query, normalized_plant_type
        )
    else:
        species_entries, query_metadata = fetch_species_entries_for_type(state_code, normalized_plant_type)

    ranked_species, strict_match_count, filter_relaxed = prioritize_species_by_plant_type(
        species_entries, normalized_plant_type
    )
    shuffled_species = list(ranked_species)
    random.shuffle(shuffled_species)

    flora_plants: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, species in enumerate(shuffled_species):
        mapped_plant = flora_species_to_plant(species, state_code=state_code, zone_hint=zone_hint, position=position)
        plant_id = mapped_plant["id"]
        if plant_id in seen_ids:
            continue
        seen_ids.add(plant_id)
        flora_plants.append(mapped_plant)
        if len(flora_plants) >= 10:
            break

    climate_profile = {
        "id": f"zip-{zip_code}",
        "label": f"ZIP {zip_code}",
        "zone": zone_hint,
        "region": "generic",
    }
    filter_metadata = {
        "plantType": normalized_plant_type,
        "plantQuery": normalized_plant_query,
        "strictMatchCount": strict_match_count,
        "filterRelaxed": filter_relaxed,
        "queryMetadata": query_metadata,
    }
    return climate_profile, flora_plants, filter_metadata


def get_climate_profile(climate_id: str | None) -> dict[str, str]:
    if not climate_id:
        return dict(DEFAULT_CLIMATE_PROFILE)
    if climate_id in DYNAMIC_CLIMATE_PROFILES:
        return DYNAMIC_CLIMATE_PROFILES[climate_id]
    return {
        "id": climate_id,
        "label": str(climate_id),
        "zone": "unknown",
        "region": "generic",
    }


def recommend_plants(climate_profile: dict[str, str]) -> list[dict[str, Any]]:
    _ = climate_profile
    return []


def compute_metrics(
    climate_profile: dict[str, str], placed_plants_payload: list[dict[str, Any]]
) -> dict[str, int]:
    _ = climate_profile
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

    native_weight = sum(weight for plant, weight in resolved_entries if plant.get("nativeRegions"))
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
    plant_type_options = [
        {"id": option_id, "label": option_details["label"]}
        for option_id, option_details in PLANT_TYPE_OPTIONS.items()
    ]
    return jsonify(
        {
            "climateOptions": CLIMATE_OPTIONS,
            "plantLibrary": PLANT_LIBRARY,
            "plantTypeOptions": plant_type_options,
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
    requested_plant_type = request.args.get("plantType") or request.args.get("plant_type")
    requested_plant_query = request.args.get("plantQuery") or request.args.get("plant_query")
    normalized_plant_type = normalize_plant_type(requested_plant_type)
    normalized_plant_query = normalize_plant_query(requested_plant_query)
    if requested_plant_type and not normalized_plant_type:
        return (
            jsonify(
                {
                    "error": "Unsupported plantType. Use one of: flower, fruit, bush, tree, vine, grass, succulent.",
                    "plantType": requested_plant_type,
                }
            ),
            400,
        )
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
            climate_profile, flora_plants, filter_metadata = flora_recommendations_for_zip(
                zip_code, plant_type=normalized_plant_type, plant_query=normalized_plant_query
            )
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
                "floraEnabled": True,
                "source": "flora",
                "plantType": normalized_plant_type,
                "plantQuery": normalized_plant_query,
                "filterRelaxed": filter_metadata["filterRelaxed"],
                "strictMatchCount": filter_metadata["strictMatchCount"],
                "queryMetadata": filter_metadata.get("queryMetadata"),
            }
        )

    climate_profile = get_climate_profile(climate_id)
    return jsonify(
        {
            "climate": climate_profile,
            "plants": recommend_plants(climate_profile),
            "source": "local",
            "plantType": normalized_plant_type,
            "plantQuery": normalized_plant_query,
        }
    )


@app.get("/api/recommendations/zipcode")
def recommendations_by_zip_code() -> Any:
    zip_code = normalize_zip_code(request.args.get("zipCode") or request.args.get("zip_code"))
    requested_plant_type = request.args.get("plantType") or request.args.get("plant_type")
    requested_plant_query = request.args.get("plantQuery") or request.args.get("plant_query")
    normalized_plant_type = normalize_plant_type(requested_plant_type)
    normalized_plant_query = normalize_plant_query(requested_plant_query)
    if not zip_code:
        return jsonify({"error": "A valid 5-digit zipCode is required."}), 400
    if requested_plant_type and not normalized_plant_type:
        return (
            jsonify(
                {
                    "error": "Unsupported plantType. Use one of: flower, fruit, bush, tree, vine, grass, succulent.",
                    "plantType": requested_plant_type,
                }
            ),
            400,
        )

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
        climate_profile, flora_plants, filter_metadata = flora_recommendations_for_zip(
            zip_code, plant_type=normalized_plant_type, plant_query=normalized_plant_query
        )
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
            "floraEnabled": True,
            "source": "flora",
            "plantType": normalized_plant_type,
            "plantQuery": normalized_plant_query,
            "filterRelaxed": filter_metadata["filterRelaxed"],
            "strictMatchCount": filter_metadata["strictMatchCount"],
            "queryMetadata": filter_metadata.get("queryMetadata"),
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
