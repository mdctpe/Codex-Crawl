from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

DEFAULT_TARGET_USAGES: tuple[str, ...] = ()
DEFAULT_MIN_CONSTRUCTION_COST = 0
DEFAULT_MAX_PROJECTS = 50
DEFAULT_NLMA_BMLIC_API_URL = (
    "https://cloudbm.nlma.gov.tw/eweb/OpenData/OAS/EIX_RSAPI_V1/opendata/bmlic"
)
DEFAULT_NEW_TAIPEI_JSON_URL = (
    "https://data.ntpc.gov.tw/api/datasets/"
    "C1487D7B-FFF1-43D3-A2CE-4716EAB4D286/json"
)
TAICHUNG_JSON_URL = (
    "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download"
    "?rid=0bf1850e-4295-433a-8ebc-9cdf9192eac5"
)
REQUEST_TIMEOUT_SECONDS = 45
DEFAULT_RESULTS_PATH = "results/results.json"
DEFAULT_NEW_TAIPEI_PAGE_SIZE = 200
DEFAULT_NEW_TAIPEI_MAX_PAGES = 3


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


def write_results(results_path: str, payload: dict[str, Any]) -> None:
    output_path = Path(results_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote crawler results to: {output_path}")


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


def fetch_nlma_records(
    api_url: str,
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    print(f"[NLMA] 抓取中: {api_url}")
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
        print(f"[NLMA] 抓取失敗: {exc}")
        return [], {
            "status": "request_error",
            "error": str(exc),
            "request_params": params,
        }

    try:
        payload = response.json()
    except ValueError as exc:
        print(f"[NLMA] 回傳不是 JSON: {exc}")
        return [], {
            "status": "invalid_json",
            "error": str(exc),
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "body_preview": response.text[:500],
            "request_params": params,
        }

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

    normalized_records = [record for record in records if isinstance(record, dict)]
    print(f"[NLMA] 取得 {len(normalized_records)} 筆原始資料")
    return normalized_records, {
        "status": "ok",
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "record_count": len(normalized_records),
        "request_params": params,
    }


def normalize_nlma_permit(record: dict[str, Any]) -> dict[str, Any]:
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
            or "unknown"
        ).strip(),
        "project_name": str(
            record.get("projectName")
            or record.get("工程名稱")
            or record.get("caseName")
            or "未命名建案"
        ).strip(),
        "developer_name": str(
            record.get("developerName")
            or record.get("起造人")
            or record.get("owner")
            or record.get("申請人")
            or "待補"
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
        "source_tag": "NLMA",
    }


def fetch_new_taipei_records(
    api_url: str,
    page_size: int,
    max_pages: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    print(f"[新北市] 抓取中: {api_url}")
    records: list[dict[str, Any]] = []
    pages_fetched = 0
    safe_page_size = max(page_size, 1)
    safe_max_pages = max(max_pages, 1)

    for page in range(safe_max_pages):
        params = {"page": page, "size": safe_page_size}
        try:
            response = requests.get(
                api_url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"[新北市] 第 {page} 頁抓取失敗: {exc}")
            return records, {
                "status": "request_error",
                "error": str(exc),
                "page": page,
                "pages_fetched": pages_fetched,
                "record_count": len(records),
                "request_params": params,
            }

        try:
            payload = response.json()
        except ValueError as exc:
            print(f"[新北市] 第 {page} 頁回傳不是 JSON: {exc}")
            return records, {
                "status": "invalid_json",
                "error": str(exc),
                "page": page,
                "pages_fetched": pages_fetched,
                "record_count": len(records),
                "http_status": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "body_preview": response.text[:500],
                "request_params": params,
            }

        if isinstance(payload, list):
            page_records = payload
        elif isinstance(payload, dict):
            for key in ("data", "records", "rows", "results"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    page_records = candidate
                    break
            else:
                page_records = []
        else:
            page_records = []

        normalized_page_records = [
            record for record in page_records if isinstance(record, dict)
        ]
        records.extend(normalized_page_records)
        pages_fetched += 1
        print(f"[新北市] 第 {page} 頁取得 {len(normalized_page_records)} 筆")

        if len(normalized_page_records) < safe_page_size:
            break

    print(f"[新北市] 合計 {len(records)} 筆原始資料")
    return records, {
        "status": "ok",
        "record_count": len(records),
        "pages_fetched": pages_fetched,
        "page_size": safe_page_size,
        "max_pages": safe_max_pages,
    }


def normalize_new_taipei_permit(record: dict[str, Any]) -> dict[str, Any]:
    site_address = str(
        record.get("house_address")
        or record.get("building_site")
        or record.get("address")
        or ""
    ).strip() or "地址待補齊"

    usage = str(
        record.get("use_of_buildings") or record.get("building_use") or ""
    ).strip()
    permit_number = str(record.get("license_number") or "unknown").strip()

    return {
        "permit_number": permit_number,
        "project_name": str(
            record.get("project_name")
            or record.get("building_site")
            or record.get("house_address")
            or permit_number
        ).strip(),
        "developer_name": str(
            record.get("proprietor") or record.get("applicant") or "待補"
        ).strip(),
        "architect_name": str(
            record.get("designer") or record.get("supervisor") or ""
        ).strip(),
        "site_address": site_address,
        "construction_cost": parse_number(record.get("project_cost") or 0),
        "permit_issued_at": normalize_date(
            record.get("date_licensing") or record.get("date_the_permit")
        ),
        "usage": usage,
        "region": "新北市",
        "source_tag": "新北市",
        "constructor_name": str(record.get("constructor") or "").strip(),
        "land_use_zoning": str(record.get("land_use_zoning") or "").strip(),
    }


def fetch_taichung_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    print(f"[台中市] 抓取中: {TAICHUNG_JSON_URL}")
    try:
        response = requests.get(TAICHUNG_JSON_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"[台中市] 抓取失敗: {exc}")
        return [], {
            "status": "request_error",
            "error": str(exc),
        }
    except ValueError as exc:
        print(f"[台中市] 回傳不是 JSON: {exc}")
        return [], {
            "status": "invalid_json",
            "error": str(exc),
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "body_preview": response.text[:500],
        }

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

    normalized_records = [record for record in records if isinstance(record, dict)]
    print(f"[台中市] 取得 {len(normalized_records)} 筆原始資料")
    return normalized_records, {
        "status": "ok",
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "record_count": len(normalized_records),
    }


def normalize_taichung_permit(record: dict[str, Any]) -> dict[str, Any]:
    site_address = str(
        record.get("起造人地址") or record.get("基地地址") or record.get("address") or ""
    ).strip() or "地址待補齊"

    usage = str(record.get("建築物用途") or record.get("用途") or "").strip()
    cost = parse_number(record.get("工程造價(元)") or record.get("工程造價") or 0)

    issued_raw = (
        record.get("發照日期") or record.get("核發日期") or record.get("permit_date") or ""
    )

    return {
        "permit_number": str(
            record.get("核發執照字號") or record.get("執照字號") or "unknown"
        ).strip(),
        "project_name": str(
            record.get("工程名稱") or record.get("建案名稱") or "未命名建案"
        ).strip(),
        "developer_name": str(
            record.get("起造人代表人") or record.get("起造人") or "待補"
        ).strip(),
        "architect_name": str(record.get("設計人") or record.get("建築師") or "").strip(),
        "site_address": site_address,
        "construction_cost": cost,
        "permit_issued_at": normalize_date(issued_raw),
        "usage": usage,
        "region": "台中市",
        "source_tag": "台中市",
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
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": api_key, "language": "zh-TW"},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [Maps] 失敗 '{query}': {exc}")
        return None

    payload = response.json()
    results = payload.get("results", [])
    if not results:
        status = payload.get("status", "UNKNOWN")
        print(f"  [Maps] 無結果 '{query}' (status: {status})")
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


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Crawler started at: {started_at}")
    load_environment()
    results_path = get_env("RESULTS_PATH", DEFAULT_RESULTS_PATH)

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
    new_taipei_url = get_env("NEW_TAIPEI_JSON_URL", DEFAULT_NEW_TAIPEI_JSON_URL)
    new_taipei_page_size = parse_int_env(
        "NEW_TAIPEI_PAGE_SIZE", DEFAULT_NEW_TAIPEI_PAGE_SIZE
    )
    new_taipei_max_pages = parse_int_env(
        "NEW_TAIPEI_MAX_PAGES", DEFAULT_NEW_TAIPEI_MAX_PAGES
    )

    results_payload: dict[str, Any] = {
        "started_at": started_at,
        "finished_at": None,
        "status": "running",
        "results_path": results_path,
        "sources": {
            "nlma": {"url": nlma_url, "fetch": {}},
            "new_taipei": {
                "url": new_taipei_url,
                "page_size": new_taipei_page_size,
                "max_pages": new_taipei_max_pages,
                "fetch": {},
            },
            "taichung": {"url": TAICHUNG_JSON_URL, "fetch": {}},
        },
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "min_construction_cost": min_cost,
            "max_projects": max_projects,
            "target_usages": list(target_usages),
        },
        "supabase": {
            "configured": supabase_ready,
            "missing": [
                name
                for name, value in (
                    ("SUPABASE_URL", supabase_url),
                    ("SUPABASE_SERVICE_KEY", supabase_key),
                )
                if not value
            ],
        },
        "google_maps": {
            "configured": bool(google_key),
        },
        "raw_record_count": 0,
        "matched_record_count": 0,
        "results": [],
    }

    print(f"篩選條件: {start_date} ~ {end_date}, 最低造價={min_cost:,}, 最多={max_projects}")

    if not google_key:
        print("⚠ 未設定 GOOGLE_MAPS_API_KEY，跳過 Google Maps 補強。")

    all_permits: list[dict[str, Any]] = []

    nlma_raw, nlma_meta = fetch_nlma_records(nlma_url, start_date, end_date)
    results_payload["sources"]["nlma"]["fetch"] = nlma_meta
    all_permits += [normalize_nlma_permit(record) for record in nlma_raw]

    new_taipei_raw, new_taipei_meta = fetch_new_taipei_records(
        new_taipei_url,
        new_taipei_page_size,
        new_taipei_max_pages,
    )
    results_payload["sources"]["new_taipei"]["fetch"] = new_taipei_meta
    all_permits += [normalize_new_taipei_permit(record) for record in new_taipei_raw]

    taichung_raw, taichung_meta = fetch_taichung_records()
    results_payload["sources"]["taichung"]["fetch"] = taichung_meta
    all_permits += [normalize_taichung_permit(record) for record in taichung_raw]

    results_payload["raw_record_count"] = len(all_permits)
    print(f"\n合計原始資料: {len(all_permits)} 筆")

    if not all_permits:
        print("無任何原始資料。Exiting successfully.")
        results_payload["status"] = "no_source_records"
        results_payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_results(results_path, results_payload)
        return 0

    filtered = [
        permit
        for permit in all_permits
        if permit_matches(permit, start_date, end_date, min_cost, target_usages)
    ]
    filtered.sort(key=lambda permit: int(permit["construction_cost"]), reverse=True)
    results_payload["matched_record_count"] = len(filtered)

    if not filtered:
        print("篩選後無符合資料。Exiting successfully.")
        results_payload["status"] = "no_matching_permits"
        results_payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_results(results_path, results_payload)
        return 0

    print(f"✓ 符合條件: {len(filtered)} 筆，處理前 {max_projects} 筆。\n")

    selected_results: list[dict[str, Any]] = []
    for permit in filtered[:max_projects]:
        print(
            f"[{permit['source_tag']}] {permit['project_name']} | "
            f"{permit['developer_name']} | "
            f"造價: {permit['construction_cost']:,} | "
            f"{permit['site_address']}"
        )

        result_permit = dict(permit)
        maps_data = None
        if google_key:
            query = f"{permit['site_address']} {permit['developer_name']}"
            result_permit["google_maps_query"] = query
            maps_data = search_google_maps(query, google_key)
            if maps_data:
                print(f"  Maps: {maps_data['name']} | {maps_data['formatted_address']}")
                result_permit["google_maps_match"] = maps_data
            else:
                result_permit["google_maps_match"] = None

        if supabase_ready:
            upsert_to_supabase(supabase_url, supabase_key, permit, maps_data)

        selected_results.append(result_permit)

    results_payload["results"] = selected_results
    results_payload["status"] = "completed"
    results_payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_results(results_path, results_payload)
    print("\nCrawler completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
