from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Any

import requests

DEFAULT_TARGET_USAGES: tuple[str, ...] = ()
DEFAULT_MIN_CONSTRUCTION_COST = 0
DEFAULT_MAX_PROJECTS = 50
DEFAULT_NLMA_BMLIC_API_URL = (
    "https://cloudbm.nlma.gov.tw/eweb/OpenData/OAS/EIX_RSAPI_V1/opendata/bmlic"
)

TAICHUNG_JSON_URL = (
    "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download"
    "?rid=0bf1850e-4295-433a-8ebc-9cdf9192eac5"
)


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def get_env(name: str, fallback: str) -> str:
    return os.getenv(name, "").strip() or fallback


def parse_int_env(name: str, fallback: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return fallback
    try:
        return int(raw.replace(",", ""))
    except ValueError:
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


# ── NLMA 全國建照 ─────────────────────────────────────────────────────────────

def fetch_nlma_records(api_url: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    print(f"[NLMA] 抓取中: {api_url}")
    try:
        response = requests.get(
            api_url,
            params={"startDate": start_date, "endDate": end_date},
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"[NLMA] 抓取失敗: {exc}")
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

    print(f"[NLMA] 取得 {len(records)} 筆原始資料")
    return [r for r in records if isinstance(r, dict)]


def normalize_nlma_permit(record: dict[str, Any]) -> dict[str, Any]:
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
            record.get("licenseNo") or "unknown"
        ).strip(),
        "project_name": str(
            record.get("projectName") or record.get("工程名稱") or
            record.get("caseName") or "未命名建案"
        ).strip(),
        "developer_name": str(
            record.get("developerName") or record.get("起造人") or
            record.get("owner") or record.get("申請人") or "待補"
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
        "source_tag": "NLMA",
    }


# ── 台中市建照 ────────────────────────────────────────────────────────────────

def fetch_taichung_records() -> list[dict[str, Any]]:
    print(f"[台中市] 抓取中: {TAICHUNG_JSON_URL}")
    try:
        response = requests.get(TAICHUNG_JSON_URL, timeout=45)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"[台中市] 抓取失敗: {exc}")
        return []

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        for key in ("data", "records", "rows", "results"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                records = candidate
                break
        else:
            records = []
    else:
        records = []

    print(f"[台中市] 取得 {len(records)} 筆原始資料")
    return [r for r in records if isinstance(r, dict)]


def normalize_taichung_permit(record: dict[str, Any]) -> dict[str, Any]:
    site_address = str(
        record.get("起造人地址") or record.get("基地地址") or
        record.get("address") or ""
    ).strip() or "地址待補齊"

    usage = str(record.get("建築物用途") or record.get("用途") or "").strip()
    cost = parse_number(record.get("工程造價(元)") or record.get("工程造價") or 0)

    issued_raw = (
        record.get("發照日期") or record.get("核發日期") or
        record.get("permit_date") or ""
    )

    return {
        "permit_number": str(record.get("核發執照字號") or record.get("執照字號") or "unknown").strip(),
        "project_name": str(record.get("工程名稱") or record.get("建案名稱") or "未命名建案").strip(),
        "developer_name": str(record.get("起造人代表人") or record.get("起造人") or "待補").strip(),
        "architect_name": str(record.get("設計人") or record.get("建築師") or "").strip(),
        "site_address": site_address,
        "construction_cost": cost,
        "permit_issued_at": normalize_date(issued_raw),
        "usage": usage,
        "region": "台中市",
        "source_tag": "台中市",
    }


# ── 篩選 + Supabase ───────────────────────────────────────────────────────────

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
    except Exception as exc:
        print(f"  [Maps] 失敗 '{query}': {exc}")
        return None
    results = response.json().get("results", [])
    if not results:
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
        "source": f"建照-{permit['source_tag']}-{usage[:4]}",
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
            print(f"  ✓ Supabase: {permit['developer_name']} ({permit['source_tag']})")
        else:
            print(f"  ✗ 失敗 ({resp.status_code}): {resp.text[:200]}")
    except Exception as exc:
        print(f"  ✗ 連線錯誤: {exc}")


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"Crawler started at: {datetime.now(timezone.utc).isoformat()}")
    load_environment()

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    supabase_ready = bool(supabase_url and supabase_key)

    if supabase_ready:
        print("✓ Supabase 設定確認，資料將寫入 leads 表。")
    else:
        print("⚠ Supabase 未設定，資料只會 print。")

    start_date = get_env("PERMIT_START_DATE", "2023-01-01")
    end_date = get_env("PERMIT_END_DATE", datetime.now(timezone.utc).date().isoformat())
    min_cost = parse_int_env("MIN_CONSTRUCTION_COST", DEFAULT_MIN_CONSTRUCTION_COST)
    max_projects = parse_int_env("MAX_PROJECTS", DEFAULT_MAX_PROJECTS)
    target_usages = parse_list_env("TARGET_USAGES", DEFAULT_TARGET_USAGES)
    google_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    nlma_url = get_env("NLMA_BMLIC_API_URL", DEFAULT_NLMA_BMLIC_API_URL)

    print(f"篩選條件: {start_date} ~ {end_date}, 最低造價={min_cost:,}, 最多={max_projects}")

    if not google_key:
        print("⚠ 未設定 GOOGLE_MAPS_API_KEY，跳過 Google Maps 補強。")

    # ── 抓資料：NLMA + 台中市 ──
    all_permits: list[dict[str, Any]] = []

    nlma_raw = fetch_nlma_records(nlma_url, start_date, end_date)
    all_permits += [normalize_nlma_permit(r) for r in nlma_raw]

    taichung_raw = fetch_taichung_records()
    all_permits += [normalize_taichung_permit(r) for r in taichung_raw]

    print(f"\n合計原始資料: {len(all_permits)} 筆")

    # ── 篩選 ──
    filtered = [
        p for p in all_permits
        if permit_matches(p, start_date, end_date, min_cost, target_usages)
    ]
    filtered.sort(key=lambda p: int(p["construction_cost"]), reverse=True)

    if not filtered:
        print("篩選後無符合資料。Exiting successfully.")
        return 0

    print(f"✓ 符合條件: {len(filtered)} 筆，處理前 {max_projects} 筆。\n")

    # ── 處理 + 寫入 ──
    for permit in filtered[:max_projects]:
        print(
            f"[{permit['source_tag']}] {permit['project_name']} | "
            f"{permit['developer_name']} | "
            f"造價: {permit['construction_cost']:,} | "
            f"{permit['site_address']}"
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
