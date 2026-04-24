from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

TEST_PROJECTS = [
    {"name": "Taipei Star", "location": "Daan District, Taipei City"},
    {"name": "Cathay No. 1", "location": "Xinyi District, Taipei City"},
]


def load_environment() -> None:
    """Load local environment variables when python-dotenv is available."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("python-dotenv is not installed; skipping .env loading.")
        return

    load_dotenv()


def configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def search_google_maps(query: str, api_key: str) -> dict[str, str | None] | None:
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": api_key,
        "language": "zh-TW",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Google Maps request failed for '{query}': {exc}")
        return None

    payload = response.json()
    results = payload.get("results", [])

    if not results:
        status = payload.get("status", "UNKNOWN")
        print(f"Google Maps returned no results for '{query}' (status: {status}).")
        return None

    place = results[0]
    return {
        "formatted_address": place.get("formatted_address"),
        "name": place.get("name"),
        "place_id": place.get("place_id"),
    }


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Crawler started at: {started_at}")

    load_environment()

    supabase_required = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    supabase_missing = [name for name in supabase_required if not configured(name)]

    if supabase_missing:
        print("Supabase configuration is incomplete.")
        print(f"Missing environment variables: {', '.join(supabase_missing)}")
        print("Continuing because this scaffold does not write to Supabase yet.")
    else:
        print("Supabase configuration found.")
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")

    google_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not google_key:
        print("Missing GOOGLE_MAPS_API_KEY; skipping Google Maps enrichment.")
        print("Crawler configuration check completed successfully.")
        return 0

    for project in TEST_PROJECTS:
        query = f"{project['location']} {project['name']}"
        print(f"Searching Google Maps for: {query}")
        map_data = search_google_maps(query, google_key)

        if map_data:
            print(
                "Matched project: "
                f"name={map_data['name']}, "
                f"address={map_data['formatted_address']}, "
                f"place_id={map_data['place_id']}"
            )
        else:
            print("No Google Maps match found for this project.")

    print("Crawler run completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
