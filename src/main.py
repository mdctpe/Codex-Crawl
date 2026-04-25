from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
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
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def get_env(name: str, fallback: str) -> str:
    return os.getenv(name, "").strip() or fallback


def parse_int_env(name: str, fallback: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return fallback
    try:
        return int(raw.replace(",", ""))
    except ValueError:
        print(f"Invalid integer for {name}: {raw}. Using fallback {fallback}.")
        return fallback


def parse_list_env(name: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return fallback
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
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
        for sep in ("/", "-", "."):
            parts = candidate.split(sep)
            if len(parts) != 3:
                continue
            year, month, day = parts
            if len(year) == 3 and year.isdigit() and month.isdigit() and day.isdigit():
                try:
                    return date(int(year) + 1911, int(month), int(day)).isoformat()
                except ValueError:
                    continue
    return raw


def fetch_government_records(
    api_url: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    params = {"startDate": start_date, "endDate": end_date}
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
        print(f"Response is not valid JSON: {exc}")
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
    return [r for r in records if isinstance(r, dict)]


def normalize_remote_permit(record: dict[str, Any]) -> dict[str, Any]:
    site_address = str(
        record.get("siteAddress") or record.get("address") or
        record.get("addr") or record.get("建築地點") or record.get("地點") or ""
    ).strip() or "地址待補齊"

    usage = str(
        record.get("usage") or record.get("用途") or
        record.get("buildingUse") or record.get("buildUse") or ""
    ).strip()

    return {
        "permit_number": str(
            record.get("permitNumber") or record.get("執照字號") or
            record.get("licenseNo") or "unknown-permit"
        ).strip(),
        "project_name": str(
            record.get("projectName") or record.get("工程名稱") or
            record.get("caseName") or record.get("建案名稱") or "未命名建案"
        ).strip(),
        "developer_name": str(
            record.get("developerName") or record.get("起造人") or
            record.get("owner") or record.get("申請人") or "待補起造人"
        ).strip(),
        "architect_name": str(
            record.get("architectName") or record.get("建築師") or
            record.get("designer") or ""
        ).strip(),
        "site_address": site_address,
        "construction_cost": parse_number(
            record.get("constructionCost") or record.get("造價") or
            record.get("cost") or record.get("totalCost")
        ),
        "permit_issued_at": normalize_date(
            record.get("permitIssuedAt") or record.get("issueDate") or
            record.get("核照日期") or record.get("發照日期")
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
    if target_usages and not any(kw in usage for kw in target_usages):
        return False
    return True


def search_google_maps(query: str, api_key: str) -> dict[str, str | None] | None:
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": api_key, "language": "zh-TW"},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Google Maps request failed for '{query}': {exc}")
        return None
    payload = response.json()
    results = payload.get("results", [])
    if not results:
        print(f"Google Maps no results for '{query}' (status: {payload.get('status')}).")
        return None
    place = results[0]
    return {
        "formatted_address": place.get("formatted_address"),
        "name": place.get("name"),
        "place_id": place.get("place_id"),
    }


def upsert_to_supabase(
    supabase_url: str,
    service_key: str,
    permit: dict[str, Any],
    maps_data: dict[str, str | None] | None,
) -> None:
    """把一筆建照資料寫入 Supabase leads 表"""
    usage = permit["usage"]
    if "住宅" in usage:
        project_type = "residential"
    elif "旅館" in usage:
        project_type = "hotel"
    elif "商" in usage or "辦" in usage:
        project_type = "office"
    else:
        project_type = "other"

    record: dict[str, Any] = {
        "company_name": permit["developer_name"],
        "contact_person": permit["architect_name"] or None,
        "address": permit["site_address"],
        "source": f"建照-{usage[:4]}",
        "status": "new",
        "heat_score": min(int(permit["construction_cost"] / 10_000_000), 100),
        "project_name": permit["project_name"],
        "project_budget": permit["construction_cost"],
        "project_type": project_type,
    }

    if maps_data:
        place_id = maps_data.get("place_id")
        record["google_place_id"] = place_id
        if place_id:
            record["google_maps_url"] = (
                f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            )

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    try:
        resp = requests.post(
            f"{supabase_url}/rest/v1/leads",
            headers=headers,
            data=json.dumps(record),
            timeout=15,
        )
        if resp.ok:
            print(f"  ✓ Supabase: {permit['developer_name']} ({permit['project_name']})")
        else:
            print(f"  ✗ Supabase 寫入失敗 ({resp.status_code}): {resp.text[:200]}")
    except Exception as exc:
        print(f"  ✗ Supabase 連線錯誤: {exc}")


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Crawler started at: {started_at}")

    load_environment()

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    supabase_ready = bool(supabase_url and supabase_key)

    if supabase_ready:
        print("✓ Supabase 設定確認，資料將寫入 leads 表。")
    else:
        print("⚠ Supabase 未設定，資料只會 print，不會寫入。")

    api_url = get_env("NLMA_BMLIC_API_URL", DEFAULT_NLMA_BMLIC_API_URL)
    start_date = get_env("PERMIT_START_DATE", "2023-01-01")
    end_date = get_env("PERMIT_END_DATE", datetime.now(timezone.utc).date().isoformat())
    min_cost = parse_int_env("MIN_CONSTRUCTION_COST", DEFAULT_MIN_CONSTRUCTION_COST)
    max_projects = parse_int_env("MAX_PROJECTS", DEFAULT_MAX_PROJECTS)
    target_usages = parse_list_env("TARGET_USAGES", DEFAULT_TARGET_USAGES)
    google_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

    print(f"Source: {api_url}")
    print(f"Filters: {start_date} ~ {end_date}, min_cost={min_cost:,}, max={max_projects}")

    if not google_key:
        print("⚠ 未設定 GOOGLE_MAPS_API_KEY，跳過 Google Maps 補強。")

    raw_records = fetch_government_records(api_url, start_date, end_date)
    if not raw_records:
        print("No records returned. Exiting successfully.")
        return 0

    permits = [normalize_remote_permit(r) for r in raw_records]
    filtered = [
        p for p in permits
        if permit_matches(p, start_date, end_date, min_cost, target_usages)
    ]
    filtered.sort(key=lambda p: int(p["construction_cost"]), reverse=True)

    if not filtered:
        print("Records fetched but none matched the filters.")
        return 0

    print(f"\n✓ 符合條件：{len(filtered)} 筆，處理前 {max_projects} 筆。\n")

    for permit in filtered[:max_projects]:
        print(
            f"建案: {permit['project_name']} | "
            f"建商: {permit['developer_name']} | "
            f"造價: {permit['construction_cost']:,} | "
            f"地址: {permit['site_address']}"
        )

        maps_data = None
        if google_key:
            query = f"{permit['site_address']} {permit['developer_name']}"
            maps_data = search_google_maps(query, google_key)
            if maps_data:
                print(f"  Maps: {maps_data['name']} | {maps_data['formatted_address']}")

        if supabase_ready:
            upsert_to_supabase(supabase_url, supabase_key, permit, maps_data)

    print("\nCrawler completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
