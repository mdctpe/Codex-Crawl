from __future__ import annotations

import os
from datetime import date
from datetime import datetime, timezone
from typing import Any

import requests

DEFAULT_NLMA_BMLIC_API_URL = (
    "https://cloudbm.nlma.gov.tw/eweb/OpenData/OAS/EIX_RSAPI_V1/opendata/bmlic"
)
DEFAULT_TARGET_USAGES = ("旅館", "百貨", "集合住宅", "商業", "商辦")
DEFAULT_MIN_CONSTRUCTION_COST = 50_000_000
DEFAULT_MAX_PROJECTS = 10
REQUEST_TIMEOUT_SECONDS = 45


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


def get_env(name: str, fallback: str) -> str:
    return os.getenv(name, "").strip() or fallback


def parse_int_env(name: str, fallback: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return fallback

    try:
        return int(raw_value.replace(",", ""))
    except ValueError:
        print(f"Invalid integer for {name}: {raw_value}. Using fallback {fallback}.")
        return fallback


def parse_list_env(name: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return fallback

    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return values or fallback


def parse_number(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)

    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized:
            return 0
        try:
            return int(float(normalized))
        except ValueError:
            return 0

    return 0


def normalize_date(value: Any) -> str:
    if value is None:
        return ""

    raw = str(value).strip()
    if not raw:
        return ""

    candidates = [raw, raw.split("T")[0], raw.split(" ")[0]]
    formats = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d")

    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                continue

        for separator in ("/", "-", "."):
            parts = candidate.split(separator)
            if len(parts) != 3:
                continue

            year, month, day = parts
            if len(year) == 3 and year.isdigit() and month.isdigit() and day.isdigit():
                try:
                    gregorian_year = int(year) + 1911
                    return date(gregorian_year, int(month), int(day)).isoformat()
                except ValueError:
                    continue

    return raw


def fetch_government_records(
    api_url: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    params = {
        "startDate": start_date,
        "endDate": end_date,
    }

    try:
        response = requests.get(
            api_url,
            params=params,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Government permit request failed: {exc}")
        return []

    try:
        payload = response.json()
    except ValueError as exc:
        print(f"Government permit response is not valid JSON: {exc}")
        return []

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key in ("data", "rows", "results", "records"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                records = candidate
                break
        else:
            records = []
    else:
        records = []

    return [record for record in records if isinstance(record, dict)]


def normalize_remote_permit(record: dict[str, Any]) -> dict[str, Any]:
    site_address = str(
        record.get("siteAddress")
        or record.get("address")
        or record.get("addr")
        or record.get("建築地點")
        or record.get("地點")
        or ""
    ).strip() or "地址待補齊"

    usage = str(
        record.get("usage")
        or record.get("用途")
        or record.get("buildingUse")
        or record.get("buildUse")
        or ""
    ).strip()

    return {
        "permit_number": str(
            record.get("permitNumber")
            or record.get("執照字號")
            or record.get("licenseNo")
            or "unknown-permit"
        ).strip(),
        "project_name": str(
            record.get("projectName")
            or record.get("工程名稱")
            or record.get("caseName")
            or record.get("建案名稱")
            or "未命名建案"
        ).strip(),
        "developer_name": str(
            record.get("developerName")
            or record.get("起造人")
            or record.get("owner")
            or record.get("申請人")
            or "待補起造人"
        ).strip(),
        "architect_name": str(
            record.get("architectName")
            or record.get("建築師")
            or record.get("designer")
            or ""
        ).strip(),
        "site_address": site_address,
        "construction_cost": parse_number(
            record.get("constructionCost")
            or record.get("造價")
            or record.get("cost")
            or record.get("totalCost")
        ),
        "permit_issued_at": normalize_date(
            record.get("permitIssuedAt")
            or record.get("issueDate")
            or record.get("核照日期")
            or record.get("發照日期")
        ),
        "usage": usage,
        "region": site_address[:3],
    }


def permit_matches(
    permit: dict[str, Any],
    start_date: str,
    end_date: str,
    min_cost: int,
    target_usages: tuple[str, ...],
) -> bool:
    permit_date = str(permit["permit_issued_at"]).strip()
    usage = str(permit["usage"]).strip()

    if permit["construction_cost"] < min_cost:
        return False

    if permit_date and (permit_date < start_date or permit_date > end_date):
        return False

    if target_usages and not any(keyword in usage for keyword in target_usages):
        return False

    return True


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

    api_url = get_env("NLMA_BMLIC_API_URL", DEFAULT_NLMA_BMLIC_API_URL)
    start_date = get_env("PERMIT_START_DATE", "2023-01-01")
    end_date = get_env("PERMIT_END_DATE", datetime.now(timezone.utc).date().isoformat())
    min_cost = parse_int_env("MIN_CONSTRUCTION_COST", DEFAULT_MIN_CONSTRUCTION_COST)
    max_projects = parse_int_env("MAX_PROJECTS", DEFAULT_MAX_PROJECTS)
    target_usages = parse_list_env("TARGET_USAGES", DEFAULT_TARGET_USAGES)

    print(f"Government source: {api_url}")
    print(
        "Permit filters: "
        f"start_date={start_date}, "
        f"end_date={end_date}, "
        f"min_cost={min_cost}, "
        f"max_projects={max_projects}"
    )

    raw_records = fetch_government_records(api_url, start_date, end_date)
    if not raw_records:
        print("No government permit records were returned. Exiting successfully.")
        return 0

    permits = [
        normalize_remote_permit(record)
        for record in raw_records
    ]
    filtered_permits = [
        permit
        for permit in permits
        if permit_matches(permit, start_date, end_date, min_cost, target_usages)
    ]
    filtered_permits.sort(
        key=lambda permit: int(permit["construction_cost"]),
        reverse=True,
    )

    if not filtered_permits:
        print("Government permit records were fetched, but none matched the filters.")
        return 0

    print(f"Matched {len(filtered_permits)} permit records from the government source.")

    google_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not google_key:
        print("Missing GOOGLE_MAPS_API_KEY; skipping Google Maps enrichment.")

    for permit in filtered_permits[:max_projects]:
        print(
            "Permit: "
            f"project={permit['project_name']}, "
            f"developer={permit['developer_name']}, "
            f"issued_at={permit['permit_issued_at']}, "
            f"cost={permit['construction_cost']}, "
            f"address={permit['site_address']}"
        )

        if not google_key:
            continue

        query = f"{permit['site_address']} {permit['project_name']}"
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
