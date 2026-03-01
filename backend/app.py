from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests # type: ignore
from flask import Flask, jsonify, request # type: ignore
from flask_cors import CORS # type: ignore

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


def env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw.strip())
    except ValueError:
        return default
    return max(minimum, parsed)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_env_file(PROJECT_ROOT / ".env")

FLORA_API_BASE_URL = os.getenv("FLORA_API_BASE_URL", "https://api.floraapi.com").rstrip("/")
FLORA_API_KEY = os.getenv("FLORA_API_KEY", "").strip()
OPENROUTER_API_BASE_URL = os.getenv(
    "OPENROUTER_API_BASE_URL", os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
).rstrip("/")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip() or "openai/gpt-4o-mini"
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", os.getenv("APP_URL", "")).strip()
OPENROUTER_X_TITLE = os.getenv("OPENROUTER_X_TITLE", os.getenv("APP_NAME", "EcoScape")).strip()
OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
FLORA_DEBUG_LOG_RECOMMENDATIONS = os.getenv("FLORA_DEBUG_LOG_RECOMMENDATIONS", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

FLORA_PAGE_LIMIT = env_int("FLORA_PAGE_LIMIT", 80)
FLORA_MAX_PAGES = env_int("FLORA_MAX_PAGES", 40)
FLORA_MAX_REQUESTS_PER_QUERY = env_int("FLORA_MAX_REQUESTS_PER_QUERY", 12)
FLORA_DEFAULT_BUCKET_QUERIES = min(26, env_int("FLORA_DEFAULT_BUCKET_QUERIES", 12))
REMOVE_BG_API_BASE_URL = os.getenv("REMOVE_BG_API_BASE_URL", "https://api.remove.bg/v1.0/removebg").strip()
REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY", "").strip()
REMOVE_BG_SIZE = os.getenv("REMOVE_BG_SIZE", "preview").strip() or "preview"
REMOVE_BG_TIMEOUT_SECONDS = env_int("REMOVE_BG_TIMEOUT_SECONDS", 30, minimum=5)
MAX_SPECIES_BUFFER = env_int("FLORA_MAX_SPECIES_BUFFER", 5000)
LLM_CANDIDATE_LIMIT = env_int("LLM_CANDIDATE_LIMIT", 120)
CURATED_RESULT_LIMIT = 10

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
PLANT_RATING_CACHE: dict[str, dict[str, str]] = {}
PLANT_RATING_FAILED_KEYS: set[str] = set()
SPECIES_DETAILS_CACHE: dict[str, dict[str, Any] | None] = {}
REMOVE_BG_IMAGE_CACHE: dict[str, str | None] = {}

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


def remove_bg_enabled() -> bool:
    return bool(REMOVE_BG_API_KEY)


def remove_background_from_image_url(image_url: str) -> str | None:
    cleaned_url = image_url.strip()
    if not cleaned_url:
        return None
    if cleaned_url in REMOVE_BG_IMAGE_CACHE:
        return REMOVE_BG_IMAGE_CACHE[cleaned_url]
    if not remove_bg_enabled():
        REMOVE_BG_IMAGE_CACHE[cleaned_url] = None
        return None

    try:
        response = requests.post(
            REMOVE_BG_API_BASE_URL,
            headers={"X-Api-Key": REMOVE_BG_API_KEY},
            data={
                "image_url": cleaned_url,
                "size": REMOVE_BG_SIZE,
                "format": "png",
            },
            timeout=REMOVE_BG_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        REMOVE_BG_IMAGE_CACHE[cleaned_url] = None
        return None

    if response.status_code != 200:
        REMOVE_BG_IMAGE_CACHE[cleaned_url] = None
        return None

    encoded_png = base64.b64encode(response.content).decode("ascii")
    data_url = f"data:image/png;base64,{encoded_png}"
    REMOVE_BG_IMAGE_CACHE[cleaned_url] = data_url
    return data_url


def llm_enabled() -> bool:
    return llm_provider() is not None


def llm_provider() -> str | None:
    if OPENROUTER_API_KEY:
        return "openrouter"
    if OPENAI_API_KEY:
        return "openai"
    return None


def llm_api_base_url() -> str:
    provider = llm_provider()
    if provider == "openrouter":
        return OPENROUTER_API_BASE_URL
    return OPENAI_API_BASE_URL


def llm_api_key() -> str:
    provider = llm_provider()
    if provider == "openrouter":
        return OPENROUTER_API_KEY
    return OPENAI_API_KEY


def llm_model_name() -> str | None:
    provider = llm_provider()
    if provider == "openrouter":
        return OPENROUTER_MODEL
    if provider == "openai":
        return OPENAI_MODEL
    return None


def llm_headers() -> dict[str, str]:
    provider = llm_provider()
    headers = {
        "Authorization": f"Bearer {llm_api_key()}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        if OPENROUTER_HTTP_REFERER:
            headers["HTTP-Referer"] = OPENROUTER_HTTP_REFERER
        if OPENROUTER_X_TITLE:
            headers["X-Title"] = OPENROUTER_X_TITLE
    return headers


def species_signature(species: dict[str, Any]) -> str:
    raw_identifier = (
        species.get("id")
        or species.get("species_id")
        or species.get("identifier")
        or species.get("usda_symbol")
        or species.get("scientific_name")
        or species.get("common_name")
        or ""
    )
    return str(raw_identifier).strip().lower().replace(" ", "-")


def best_common_name(species: dict[str, Any]) -> str:
    candidate_fields = (
        "common_name",
        "commonName",
        "preferred_common_name",
        "preferredCommonName",
        "vernacular_name",
        "vernacularName",
    )
    for field in candidate_fields:
        value = species.get(field)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned

    list_fields = (
        "common_names",
        "commonNames",
        "vernacular_names",
        "vernacularNames",
    )
    for field in list_fields:
        value = species.get(field)
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    continue
                cleaned = item.strip()
                if cleaned:
                    return cleaned
    return ""


def species_display_name(species: dict[str, Any]) -> str:
    common_name = best_common_name(species)
    if common_name:
        return common_name
    return "Unknown Plant"


def debug_print_flora_recommendations(
    zip_code: str,
    state_code: str,
    ranked_species: list[dict[str, Any]],
    curated_species: list[dict[str, Any]],
) -> None:
    if not (FLORA_DEBUG_LOG_RECOMMENDATIONS or app.debug):
        return

    print(
        f"[Flora Debug] ZIP {zip_code} | state={state_code} | total-ranked-candidates={len(ranked_species)}",
        flush=True,
    )
    for index, species in enumerate(ranked_species, start=1):
        print(
            f"[Flora Debug]   {index:03d}. {species_display_name(species)} | id={species_signature(species)}",
            flush=True,
        )

    print(
        f"[Flora Debug] ZIP {zip_code} | curated-top-{len(curated_species)}",
        flush=True,
    )
    for index, species in enumerate(curated_species, start=1):
        print(
            f"[Flora Debug]   TOP {index:02d}. {species_display_name(species)} | id={species_signature(species)}",
            flush=True,
        )


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


def evenly_spaced_ints(start: int, end: int, count: int) -> list[int]:
    if count <= 0:
        return []
    if end < start:
        end = start
    if count == 1:
        return [start]

    values: list[int] = []
    for idx in range(count):
        ratio = idx / (count - 1)
        value = int(round(start + (end - start) * ratio))
        if values and values[-1] == value:
            continue
        values.append(value)
    return values


def extract_total_count(payload: Any) -> int | None:
    keys = (
        "total",
        "total_count",
        "totalCount",
        "total_results",
        "totalResults",
        "num_results",
        "numResults",
    )
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return int(value)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.isdigit():
                    parsed = int(stripped)
                    if parsed > 0:
                        return parsed
        for value in payload.values():
            extracted = extract_total_count(value)
            if extracted is not None:
                return extracted
    if isinstance(payload, list):
        for item in payload:
            extracted = extract_total_count(item)
            if extracted is not None:
                return extracted
    return None


def alphabet_bucket_letters(seed_text: str, count: int) -> list[str]:
    if count <= 0:
        return []

    alphabet = "abcdefghijklmnopqrstuvwxyz"
    count = min(len(alphabet), count)
    if not seed_text:
        seed_text = "default"

    # Use a coprime step so we walk the alphabet without repeats and spread buckets.
    start = sum((index + 1) * ord(char) for index, char in enumerate(seed_text)) % len(alphabet)
    step = 11
    letters: list[str] = []
    used: set[str] = set()

    for idx in range(len(alphabet)):
        letter = alphabet[(start + idx * step) % len(alphabet)]
        if letter in used:
            continue
        letters.append(letter)
        used.add(letter)
        if len(letters) >= count:
            break
    return letters


def fetch_species_entries_paginated(
    path: str,
    params: dict[str, Any],
    max_requests: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_params = dict(params)
    raw_limit = base_params.get("limit")
    try:
        requested_limit = int(raw_limit) if raw_limit is not None else FLORA_PAGE_LIMIT
    except (ValueError, TypeError):
        requested_limit = FLORA_PAGE_LIMIT
    per_page_limit = max(1, min(requested_limit, FLORA_PAGE_LIMIT))
    base_params["limit"] = per_page_limit
    request_limit = FLORA_MAX_REQUESTS_PER_QUERY
    if isinstance(max_requests, int):
        request_limit = max(1, min(max_requests, FLORA_MAX_REQUESTS_PER_QUERY))

    combined: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    pages_fetched = 0
    requests_made = 0
    pagination_mode = "single"
    rate_limited = False
    stopped_early = False
    stop_reason = ""

    def request_budget_exhausted() -> bool:
        return requests_made >= request_limit

    def add_entries(species_entries: list[dict[str, Any]]) -> int:
        added = 0
        for species in species_entries:
            signature = species_signature(species)
            if not signature or signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            combined.append(species)
            added += 1
            if len(combined) >= MAX_SPECIES_BUFFER:
                break
        return added

    first_payload = flora_get(path, params=base_params)
    requests_made += 1
    first_entries = extract_species_list(first_payload)
    pages_fetched = 1
    add_entries(first_entries)
    total_count = extract_total_count(first_payload)
    remaining_request_budget = max(0, min(FLORA_MAX_PAGES - 1, request_limit - 1))

    if len(combined) < MAX_SPECIES_BUFFER and first_entries and remaining_request_budget > 0:
        pagination_mode = "page"
        if total_count and total_count > per_page_limit:
            estimated_pages = max(2, (total_count + per_page_limit - 1) // per_page_limit)
            page_numbers = evenly_spaced_ints(2, estimated_pages, remaining_request_budget)
        else:
            page_numbers = list(range(2, 2 + remaining_request_budget))

        page_mode_new_entries = 0
        for page in page_numbers:
            if request_budget_exhausted():
                stopped_early = True
                stop_reason = "request-budget-reached"
                break
            try:
                payload = flora_get(path, params={**base_params, "page": page})
            except requests.RequestException as exc:
                status_code = exc.response.status_code if getattr(exc, "response", None) is not None else None
                if status_code == 429:
                    rate_limited = True
                    stopped_early = True
                    stop_reason = "rate-limited-on-page"
                    break
                raise
            requests_made += 1
            entries = extract_species_list(payload)
            pages_fetched += 1
            if not entries:
                break
            new_entries = add_entries(entries)
            page_mode_new_entries += new_entries
            if len(combined) >= MAX_SPECIES_BUFFER:
                break
            if new_entries == 0:
                break

        if page_mode_new_entries == 0 and not request_budget_exhausted():
            pagination_mode = "offset"
            combined = []
            seen_signatures = set()
            add_entries(first_entries)
            pages_fetched = 1

            if total_count and total_count > per_page_limit:
                max_offset = max(per_page_limit, total_count - per_page_limit)
            else:
                # If the API does not expose total count, probe deeper offsets to reduce first-page bias.
                max_offset = per_page_limit * max(2, remaining_request_budget * 4)

            offset_values = evenly_spaced_ints(per_page_limit, max_offset, remaining_request_budget)
            for offset_value in offset_values:
                if request_budget_exhausted():
                    stopped_early = True
                    if not stop_reason:
                        stop_reason = "request-budget-reached"
                    break
                try:
                    payload = flora_get(path, params={**base_params, "offset": offset_value})
                except requests.RequestException as exc:
                    status_code = exc.response.status_code if getattr(exc, "response", None) is not None else None
                    if status_code == 429:
                        rate_limited = True
                        stopped_early = True
                        stop_reason = "rate-limited-on-offset"
                        break
                    raise
                requests_made += 1
                entries = extract_species_list(payload)
                pages_fetched += 1
                if not entries:
                    break
                new_entries = add_entries(entries)
                if len(combined) >= MAX_SPECIES_BUFFER:
                    break
                if new_entries == 0:
                    break

    metadata = {
        "paginationMode": pagination_mode,
        "pagesFetched": pages_fetched,
        "requestsMade": requests_made,
        "maxRequestsPerQuery": request_limit,
        "perPageLimit": per_page_limit,
        "resultCount": len(combined),
        "firstPageCount": len(first_entries),
        "estimatedTotalCount": total_count,
        "truncatedByMaxBuffer": len(combined) >= MAX_SPECIES_BUFFER,
        "rateLimited": rate_limited,
        "stoppedEarly": stopped_early,
        "stopReason": stop_reason or None,
    }
    return combined, metadata


def fetch_species_entries_from_candidates(
    candidates: list[tuple[str, dict[str, Any], int | None]], strategy: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    attempted: list[dict[str, Any]] = []
    successful_calls = 0
    last_error: Exception | None = None

    for path, params, max_requests in candidates:
        try:
            species_entries, pagination = fetch_species_entries_paginated(
                path,
                params=params,
                max_requests=max_requests,
            )
            successful_calls += 1
            attempted.append(
                {
                    "path": path,
                    "params": params,
                    "maxRequests": max_requests,
                    "resultCount": len(species_entries),
                    "pagination": pagination,
                }
            )
            for species in species_entries:
                signature = species_signature(species)
                if not signature:
                    continue
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                collected.append(species)
                if len(collected) >= MAX_SPECIES_BUFFER:
                    break
            if len(collected) >= MAX_SPECIES_BUFFER:
                break
        except requests.RequestException as exc:
            last_error = exc
            attempted.append(
                {
                    "path": path,
                    "params": params,
                    "maxRequests": max_requests,
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


def flora_type_search_candidates(
    state_code: str, plant_type: str | None, zip_code: str
) -> list[tuple[str, dict[str, Any], int | None]]:
    base_params = {"state": state_code, "native_only": True, "limit": FLORA_PAGE_LIMIT}
    if not plant_type:
        # Pull one page across multiple letter buckets to reduce A-first bias.
        bucket_letters = alphabet_bucket_letters(zip_code, FLORA_DEFAULT_BUCKET_QUERIES)
        offset_ceiling = max(0, (FLORA_MAX_PAGES - 1) * FLORA_PAGE_LIMIT)
        bucket_offsets = evenly_spaced_ints(0, offset_ceiling, len(bucket_letters))
        return [
            ("/v1/search", {**base_params, "q": letter, "offset": bucket_offsets[index]}, 1)
            for index, letter in enumerate(bucket_letters)
        ]

    if plant_type == "fruit":
        return [
            ("/v1/search/edible", {**base_params, "edible_part": "fruit"}, None),
            ("/v1/search", {**base_params, "q": "fruit"}, None),
            ("/v1/search", {**base_params, "q": "berry"}, None),
            ("/v1/search", {**base_params, "q": "orchard"}, None),
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
        ("/v1/search", {**base_params, "plant_habit": habit_value}, None),
        ("/v1/search", {**base_params, "habit": habit_value}, None),
        ("/v1/search", {**base_params, "q": query_term}, None),
    ]


def fetch_species_entries_for_type(
    state_code: str, plant_type: str | None, zip_code: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = flora_type_search_candidates(state_code, plant_type, zip_code)
    strategy = "typed" if plant_type else "default"
    return fetch_species_entries_from_candidates(candidates, strategy)


def flora_query_search_candidates(
    state_code: str, plant_query: str, plant_type: str | None
) -> list[tuple[str, dict[str, Any], int | None]]:
    base = {"q": plant_query, "limit": FLORA_PAGE_LIMIT}
    option = PLANT_TYPE_OPTIONS.get(plant_type) if plant_type else None
    flora_habit = option.get("flora_habit") if option else None

    staged_params: list[dict[str, Any]] = [
        {**base, "state": state_code, "native_only": True},
        {**base, "state": state_code},
        {**base},
    ]

    candidates: list[tuple[str, dict[str, Any], int | None]] = []
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
            candidates.append(("/v1/search", variant, None))
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


def unique_species_entries(species_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_entries: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    for species in species_entries:
        signature = species_signature(species)
        if not signature or signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_entries.append(species)
    return unique_entries


def species_summary_for_llm(species: dict[str, Any]) -> dict[str, Any]:
    def coerce_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    return {
        "id": species_signature(species),
        "common_name": best_common_name(species),
        "scientific_name": str(species.get("scientific_name") or "").strip(),
        "habit": str(
            species.get("habit")
            or species.get("plant_habit")
            or species.get("growth_habit")
            or species.get("growth_form")
            or ""
        ).strip(),
        "nativity_status": str(
            species.get("nativity_status") or species.get("native_status") or species.get("status") or ""
        ).strip(),
        "water_needs": str(species.get("water_usage") or species.get("water_needs") or "").strip(),
        "pollinator_value": str(
            species.get("pollinator_value")
            or species.get("pollinator_support")
            or species.get("wildlife_value")
            or species.get("wildlife_support")
            or ""
        ).strip(),
        "drought_tolerance": str(
            species.get("drought_tolerance") or species.get("drought_resistance") or ""
        ).strip(),
        "edible_parts": coerce_list(species.get("edible_parts")),
        "flower_color": str(species.get("flower_color") or species.get("flowerColor") or "").strip(),
    }


def llm_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    chunks.append(text_value)
        return "\n".join(chunks)
    return ""


def parse_json_object_from_text(raw_text: str) -> dict[str, Any] | None:
    if not raw_text:
        return None
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def species_detail_identifier_candidates(species: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for key in ("identifier", "id", "species_id", "usda_symbol", "symbol"):
        value = species.get(key)
        if value is None:
            continue
        cleaned = str(value).strip()
        if not cleaned:
            continue
        normalized = cleaned.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(cleaned)
    return candidates


def fetch_species_details(species: dict[str, Any]) -> dict[str, Any] | None:
    for identifier in species_detail_identifier_candidates(species):
        cache_key = identifier.lower()
        if cache_key in SPECIES_DETAILS_CACHE:
            return SPECIES_DETAILS_CACHE[cache_key]

        try:
            payload = flora_get(f"/v1/species/{quote(identifier, safe='')}")
        except requests.RequestException:
            SPECIES_DETAILS_CACHE[cache_key] = None
            continue

        if isinstance(payload, dict):
            SPECIES_DETAILS_CACHE[cache_key] = payload
            return payload

        SPECIES_DETAILS_CACHE[cache_key] = None
    return None


def species_description_text(species: dict[str, Any]) -> str:
    for key in ("description", "summary", "ecology", "ecology_notes", "notes"):
        value = species.get(key)
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            if cleaned:
                return cleaned

    details = fetch_species_details(species)
    if isinstance(details, dict):
        for key in (
            "description",
            "summary",
            "ecology",
            "ecology_notes",
            "notes",
            "habitat",
            "characteristics",
        ):
            value = details.get(key)
            if isinstance(value, str):
                cleaned = " ".join(value.split())
                if cleaned:
                    return cleaned
    return ""


def llm_rate_species(species: dict[str, Any]) -> dict[str, str] | None:
    if not llm_enabled():
        return None

    signature = species_signature(species)
    if not signature:
        return None

    if signature in PLANT_RATING_CACHE:
        return PLANT_RATING_CACHE[signature]
    if signature in PLANT_RATING_FAILED_KEYS:
        return None

    model_name = llm_model_name()
    if not model_name:
        return None

    payload = {
        "scientific_name": str(species.get("scientific_name") or "").strip(),
        "common_name": best_common_name(species),
        "habit": str(
            species.get("plant_habit")
            or species.get("habit")
            or species.get("growth_habit")
            or species.get("growth_form")
            or ""
        ).strip(),
        "nativity": str(
            species.get("nativity")
            or species.get("nativity_status")
            or species.get("native_status")
            or species.get("status")
            or ""
        ).strip(),
        "description": species_description_text(species),
    }

    request_body = {
        "model": model_name,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You rate plants for a sustainable garden planner. Return JSON ONLY with keys: "
                    "waterUsage, pollinatorValue, droughtResistance, carbonSequestration. "
                    "Each value must be exactly one of: Low, Medium, High. "
                    "Be conservative: if unsure, choose Medium."
                ),
            },
            {"role": "user", "content": json.dumps(payload)},
        ],
    }

    try:
        response = requests.post(
            f"{llm_api_base_url()}/chat/completions",
            headers=llm_headers(),
            json=request_body,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException:
        PLANT_RATING_FAILED_KEYS.add(signature)
        return None

    response_payload = response.json()
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        PLANT_RATING_FAILED_KEYS.add(signature)
        return None

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    parsed = parse_json_object_from_text(llm_message_text(content))
    if not parsed:
        PLANT_RATING_FAILED_KEYS.add(signature)
        return None

    def parse_rating(*keys: str) -> str:
        for key in keys:
            if key not in parsed:
                continue
            return normalize_rating(parsed.get(key), default="Medium")
        return "Medium"

    ratings = {
        "waterUsage": parse_rating("waterUsage", "water_usage"),
        "pollinatorValue": parse_rating("pollinatorValue", "pollinator_value"),
        "droughtResistance": parse_rating("droughtResistance", "drought_resistance"),
        "carbonSequestration": parse_rating("carbonSequestration", "carbon_sequestration"),
    }
    PLANT_RATING_CACHE[signature] = ratings
    return ratings


def request_llm_selected_species_ids(
    candidate_species: list[dict[str, Any]],
    zip_code: str,
    state_code: str,
    plant_type: str | None,
    plant_query: str | None,
) -> tuple[list[str], str | None]:
    if not llm_enabled():
        return [], "No LLM key configured. Set OPENROUTER_API_KEY or OPENAI_API_KEY."
    model_name = llm_model_name()
    if not model_name:
        return [], "No LLM model configured."

    prompt_payload = {
        "zip_code": zip_code,
        "state_code": state_code,
        "plant_type_filter": plant_type or "any",
        "user_query": plant_query or "",
        "target_count": CURATED_RESULT_LIMIT,
        "candidates": [species_summary_for_llm(species) for species in candidate_species],
    }

    request_body = {
        "model": model_name,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You curate plants for real home gardens. Choose the 10 best plants people would likely want: "
                    "Return JSON only: {\"selected_ids\": [\"id1\", \"id2\", ...]} using only provided candidate ids."
                ),
            },
            {"role": "user", "content": json.dumps(prompt_payload)},
        ],
    }

    try:
        response = requests.post(
            f"{llm_api_base_url()}/chat/completions",
            headers=llm_headers(),
            json=request_body,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return [], str(exc)

    payload = response.json()
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return [], "LLM response did not contain choices."

    first_choice = choices[0] if isinstance(choices[0], dict) else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    parsed = parse_json_object_from_text(llm_message_text(content))
    if not parsed:
        return [], "LLM response was not parseable JSON."

    raw_ids = parsed.get("selected_ids")
    if not isinstance(raw_ids, list):
        return [], "LLM JSON did not include selected_ids."

    selected_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in raw_ids:
        normalized = str(raw_id).strip().lower().replace(" ", "-")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        selected_ids.append(normalized)
        if len(selected_ids) >= CURATED_RESULT_LIMIT:
            break
    return selected_ids, None


def heuristic_desirability_score(species: dict[str, Any], plant_type: str | None) -> float:
    score = 0.0

    common_name = best_common_name(species)
    scientific_name = str(species.get("scientific_name") or "").strip()
    if common_name:
        score += 2.2
    if scientific_name:
        score += 0.6

    nativity_text = str(
        species.get("nativity_status") or species.get("native_status") or species.get("status") or ""
    ).lower()
    if nativity_text:
        if "native" in nativity_text and "introduced" not in nativity_text and "non-native" not in nativity_text:
            score += 3.2
        if "invasive" in nativity_text:
            score -= 5.0

    water_rating = normalize_rating(species.get("water_usage") or species.get("water_needs"), default="Medium")
    score += {"Low": 2.6, "Medium": 1.4, "High": 0.2}[water_rating]

    pollinator_rating = normalize_rating(
        species.get("pollinator_value")
        or species.get("pollinator_support")
        or species.get("wildlife_value")
        or species.get("wildlife_support"),
        default="Medium",
    )
    score += {"Low": 0.5, "Medium": 1.2, "High": 2.4}[pollinator_rating]

    drought_rating = normalize_rating(
        species.get("drought_tolerance") or species.get("drought_resistance"), default="Medium"
    )
    score += {"Low": 0.4, "Medium": 1.1, "High": 1.9}[drought_rating]

    text_blob = species_text_blob(species)
    for keyword, bonus in (
        ("ornamental", 1.2),
        ("showy", 1.1),
        ("fragrant", 0.9),
        ("evergreen", 0.8),
        ("pollinator", 0.8),
        ("butterfly", 0.8),
        ("edible", 0.8),
        ("fruit", 0.6),
        ("flower", 0.6),
    ):
        if keyword in text_blob:
            score += bonus
    for keyword, penalty in (("toxic", 1.8), ("poison", 2.0), ("invasive", 4.0)):
        if keyword in text_blob:
            score -= penalty

    if plant_type and species_strict_match(species, plant_type):
        score += 2.8
    elif plant_type:
        score -= 0.6

    signature = species_signature(species)
    if signature:
        score += sum((index + 1) * ord(char) for index, char in enumerate(signature[:24])) % 17 / 100.0
    return score


def heuristic_select_species(
    candidate_species: list[dict[str, Any]],
    plant_type: str | None,
    desired_count: int,
    excluded_signatures: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded = excluded_signatures or set()
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for species in candidate_species:
        signature = species_signature(species)
        if not signature or signature in excluded:
            continue
        tie_breaker = sum(ord(char) for char in signature[:16]) % 29
        scored.append((heuristic_desirability_score(species, plant_type), tie_breaker, species))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:desired_count]]


def build_llm_candidate_pool(
    species_entries: list[dict[str, Any]],
    max_candidates: int,
) -> list[dict[str, Any]]:
    if max_candidates <= 0 or not species_entries:
        return []
    if len(species_entries) <= max_candidates:
        return species_entries

    # Spread picks across the full list so the LLM sees candidates from later pages too.
    pool: list[dict[str, Any]] = []
    used_indices: set[int] = set()
    total = len(species_entries)
    for slot in range(max_candidates):
        index = min(total - 1, int(slot * total / max_candidates))
        while index in used_indices and index < total - 1:
            index += 1
        if index in used_indices:
            continue
        used_indices.add(index)
        pool.append(species_entries[index])
    return pool


def curate_species_for_garden(
    species_entries: list[dict[str, Any]],
    zip_code: str,
    state_code: str,
    plant_type: str | None,
    plant_query: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    unique_candidates = unique_species_entries(species_entries)
    llm_candidate_pool = build_llm_candidate_pool(unique_candidates, LLM_CANDIDATE_LIMIT)
    if not unique_candidates:
        return [], {
            "selectionMethod": "heuristic",
            "llmEnabled": llm_enabled(),
            "llmModel": llm_model_name() if llm_enabled() else None,
            "llmError": "No Flora candidates available for curation.",
            "candidateCount": 0,
            "candidatePoolCount": 0,
            "curatedCount": 0,
        }

    llm_ids, llm_error = request_llm_selected_species_ids(
        llm_candidate_pool,
        zip_code=zip_code,
        state_code=state_code,
        plant_type=plant_type,
        plant_query=plant_query,
    )
    species_by_signature = {
        species_signature(species): species for species in unique_candidates if species_signature(species)
    }

    curated_species: list[dict[str, Any]] = []
    selected_signatures: set[str] = set()
    if llm_ids:
        for selected_id in llm_ids:
            species = species_by_signature.get(selected_id)
            if not species or selected_id in selected_signatures:
                continue
            selected_signatures.add(selected_id)
            curated_species.append(species)
            if len(curated_species) >= CURATED_RESULT_LIMIT:
                break

    selection_method = "llm" if curated_species else "heuristic"
    if len(curated_species) < CURATED_RESULT_LIMIT:
        curated_species.extend(
            heuristic_select_species(
                unique_candidates,
                plant_type=plant_type,
                desired_count=CURATED_RESULT_LIMIT - len(curated_species),
                excluded_signatures=selected_signatures,
            )
        )

    metadata = {
        "selectionMethod": selection_method,
        "llmEnabled": llm_enabled(),
        "llmModel": llm_model_name() if llm_enabled() else None,
        "llmError": llm_error if selection_method != "llm" else None,
        "candidateCount": len(unique_candidates),
        "candidatePoolCount": len(llm_candidate_pool),
        "curatedCount": len(curated_species),
    }
    return curated_species[:CURATED_RESULT_LIMIT], metadata


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
    display_name = best_common_name(species) or f"Plant {position + 1}"

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
    water_usage = normalize_rating(water_source, default="Medium")
    pollinator_value = normalize_rating(pollinator_source, default="Medium")
    carbon_value = normalize_rating(carbon_source, default="Medium")
    drought_value = normalize_rating(drought_source, default="Medium")
    is_flower = species_strict_match(species, "flower")

    llm_ratings = llm_rate_species(species)
    if llm_ratings:
        water_usage = llm_ratings["waterUsage"]
        pollinator_value = llm_ratings["pollinatorValue"]
        drought_value = llm_ratings["droughtResistance"]
        carbon_value = llm_ratings["carbonSequestration"]

    return {
        "id": plant_id,
        "name": display_name,
        "emoji": flora_emoji_for_species(species),
        "isFlower": is_flower,
        "zones": parse_zones(species, zone_hint),
        "nativeRegions": ["native"] if is_native else [],
        "waterUsage": water_usage,
        "pollinatorValue": pollinator_value,
        "carbonSequestration": carbon_value,
        "shadeCoverage": normalize_rating(shade_source, default="Medium"),
        "droughtResistance": drought_value,
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
        species_entries, query_metadata = fetch_species_entries_for_type(
            state_code,
            normalized_plant_type,
            zip_code,
        )

    ranked_species, strict_match_count, filter_relaxed = prioritize_species_by_plant_type(
        species_entries, normalized_plant_type
    )
    curated_species, curation_metadata = curate_species_for_garden(
        ranked_species,
        zip_code=zip_code,
        state_code=state_code,
        plant_type=normalized_plant_type,
        plant_query=normalized_plant_query,
    )
    debug_print_flora_recommendations(
        zip_code=zip_code,
        state_code=state_code,
        ranked_species=ranked_species,
        curated_species=curated_species,
    )

    flora_plants: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, species in enumerate(curated_species):
        mapped_plant = flora_species_to_plant(species, state_code=state_code, zone_hint=zone_hint, position=position)
        plant_id = mapped_plant["id"]
        if plant_id in seen_ids:
            continue
        seen_ids.add(plant_id)
        flora_plants.append(mapped_plant)
        if len(flora_plants) >= CURATED_RESULT_LIMIT:
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
        "selectionMethod": curation_metadata["selectionMethod"],
        "candidateCount": curation_metadata["candidateCount"],
        "candidatePoolCount": curation_metadata["candidatePoolCount"],
        "curatedCount": curation_metadata["curatedCount"],
        "llmEnabled": curation_metadata["llmEnabled"],
        "llmModel": curation_metadata["llmModel"],
        "llmError": curation_metadata["llmError"],
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
    # Plant size affects visual footprint, not weekly watering units.
    weekly_water_demand = round(sum(WATER_UNITS[plant["waterUsage"]] for plant, _weight in resolved_entries))

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
                },
                "llm": {
                    "enabled": llm_enabled(),
                    "provider": llm_provider(),
                    "model": llm_model_name() if llm_enabled() else None,
                },
                "removeBg": {
                    "enabled": remove_bg_enabled(),
                },
            },
        }
    )


@app.post("/api/images/remove-background")
def remove_background() -> Any:
    payload = request.get_json(silent=True) or {}
    image_url = payload.get("imageUrl") or payload.get("image_url")
    if not isinstance(image_url, str) or not image_url.strip():
        return jsonify({"error": "imageUrl is required."}), 400

    if not remove_bg_enabled():
        return jsonify({"error": "REMOVE_BG_API_KEY not configured on backend.", "removeBgEnabled": False}), 503

    removed_background_data_url = remove_background_from_image_url(image_url)
    if not removed_background_data_url:
        return jsonify({"error": "remove.bg request failed.", "removeBgEnabled": True}), 502

    return jsonify(
        {
            "imageDataUrl": removed_background_data_url,
            "removeBgEnabled": True,
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
                "selectionMethod": filter_metadata.get("selectionMethod"),
                "candidateCount": filter_metadata.get("candidateCount"),
                "candidatePoolCount": filter_metadata.get("candidatePoolCount"),
                "curatedCount": filter_metadata.get("curatedCount"),
                "llmEnabled": filter_metadata.get("llmEnabled"),
                "llmModel": filter_metadata.get("llmModel"),
                "llmError": filter_metadata.get("llmError"),
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
            "selectionMethod": filter_metadata.get("selectionMethod"),
            "candidateCount": filter_metadata.get("candidateCount"),
            "candidatePoolCount": filter_metadata.get("candidatePoolCount"),
            "curatedCount": filter_metadata.get("curatedCount"),
            "llmEnabled": filter_metadata.get("llmEnabled"),
            "llmModel": filter_metadata.get("llmModel"),
            "llmError": filter_metadata.get("llmError"),
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
