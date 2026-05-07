from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import requests

from .shared_site import write_secure_site

DEFAULT_TARGET_USAGES: tuple[str, ...] = ()
DEFAULT_MIN_CONSTRUCTION_COST = 0
DEFAULT_MAX_PROJECTS = 200
DEFAULT_NLMA_BMLIC_API_URL = (
    "https://cloudbm.nlma.gov.tw/eweb/OpenData/OAS/EIX_RSAPI_V1/opendata/bmlic"
)
DEFAULT_GCIS_COMPANY_KEYWORD_API_URL = (
    "https://data.gcis.nat.gov.tw/od/data/api/"
    "6BBA2268-1367-4B42-9CCA-BC17499EBE8C"
)
DEFAULT_GCIS_COMPANY_DETAILS_API_URL = (
    "https://data.gcis.nat.gov.tw/od/data/api/"
    "236EE382-4942-41A9-BD03-CA0709025E7C"
)
DEFAULT_NEW_TAIPEI_JSON_URL = (
    "https://data.ntpc.gov.tw/api/datasets/"
    "C1487D7B-FFF1-43D3-A2CE-4716EAB4D286/json"
)
DEFAULT_TAIPEI_HISTORY_XML_URL = (
    "https://data.taipei/api/frontstage/tpeod/dataset/"
    "resource.download?rid=2d9396af-863b-496a-9893-0d2f2a8d8b71"
)
DEFAULT_TAIPEI_CURRENT_XML_URL = (
    "https://data.taipei/api/frontstage/tpeod/dataset/"
    "resource.download?rid=43624c8e-c768-4b3c-93c4-595f5af7a9cb"
)
TAICHUNG_JSON_URL = (
    "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download"
    "?rid=0bf1850e-4295-433a-8ebc-9cdf9192eac5"
)
REQUEST_TIMEOUT_SECONDS = 45
DEFAULT_RESULTS_PATH = "results/results.json"
DEFAULT_NEW_TAIPEI_PAGE_SIZE = 200
DEFAULT_NEW_TAIPEI_MAX_PAGES = 3
DEFAULT_SITE_OUTPUT_DIR = "site"
DEFAULT_SHARED_APP_TABLE = "crawler_leads"
DEFAULT_ALLOWED_EMAIL_DOMAIN = "eonian.space"
TRACKER_STATUS_OPTIONS: tuple[str, ...] = (
    "未處理",
    "待分派",
    "待聯絡",
    "聯絡中",
    "已回覆",
    "已成交",
    "已排除",
)
COMPANY_NAME_HINTS: tuple[str, ...] = (
    "公司",
    "有限",
    "股份",
    "建設",
    "營造",
    "工程",
    "開發",
    "實業",
    "企業",
    "不動產",
    "顧問",
    "科技",
    "工業",
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


def parse_bool_env(name: str, fallback: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return fallback
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return fallback


def write_results(results_path: str, payload: dict[str, Any]) -> None:
    output_path = Path(results_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote crawler results to: {output_path}")


def default_report_path(results_path: str) -> str:
    return str(Path(results_path).with_name("report.html"))


def default_index_path(results_path: str) -> str:
    return str(Path(results_path).with_name("index.html"))


def default_tracker_path(results_path: str) -> str:
    return str(Path(results_path).with_name("tracker.csv"))


def dated_report_path(report_path: str, start_date: str, end_date: str) -> str:
    start_year = start_date[:4] if len(start_date) >= 4 else "all"
    end_year = end_date[:4] if len(end_date) >= 4 else "all"
    return str(Path(report_path).with_name(f"report-{start_year}-{end_year}.html"))


def format_count(value: Any) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def format_money(value: Any) -> str:
    amount = parse_number(value)
    if amount <= 0:
        return "未提供"
    return f"NT$ {amount:,}"


def html_attr(value: Any) -> str:
    return escape(str(value), quote=True)


def make_lead_id(result: dict[str, Any]) -> str:
    parts = (
        str(result.get("source_tag") or ""),
        str(result.get("permit_number") or ""),
        str(result.get("permit_issued_at") or ""),
        str(result.get("developer_name") or ""),
        str(result.get("site_address") or ""),
    )
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def render_source_card(name: str, data: dict[str, Any]) -> str:
    fetch = data.get("fetch", {})
    status = str(fetch.get("status") or "unknown")
    record_count = fetch.get("record_count")
    detail_parts = [f"狀態：{escape(status)}"]
    if record_count is not None:
        detail_parts.append(f"筆數：{escape(format_count(record_count))}")
    if fetch.get("error"):
        detail_parts.append(f"錯誤：{escape(str(fetch['error']))}")
    return f"""
    <div class="source-card">
      <div class="source-name">{escape(name)}</div>
      <div class="source-url">{escape(str(data.get("url") or ""))}</div>
      <div class="source-meta">{'<br>'.join(detail_parts)}</div>
    </div>
    """


def render_result_card(result: dict[str, Any]) -> str:
    registry_meta = result.get("gcis_company_registry", {})
    registry_match = registry_meta.get("match") if isinstance(registry_meta, dict) else None
    maps_match = result.get("google_maps_match")

    detail_rows = [
        ("來源", result.get("source_tag") or "未提供"),
        ("建案名稱", result.get("project_name") or "未提供"),
        ("起造人", result.get("developer_name") or "未提供"),
        ("建築師", result.get("architect_name") or "未提供"),
        ("地址", result.get("site_address") or "未提供"),
        ("造價", format_money(result.get("construction_cost"))),
        ("用途", result.get("usage") or "未提供"),
        ("發照日期", result.get("permit_issued_at") or "未提供"),
        ("執照字號", result.get("permit_number") or "未提供"),
    ]
    if result.get("land_use_zoning"):
        detail_rows.append(("使用分區", result.get("land_use_zoning") or "未提供"))
    if result.get("constructor_name"):
        detail_rows.append(("承造人", result.get("constructor_name") or "未提供"))
    details_html = "".join(
        f"<div class=\"detail-row\"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>"
        for label, value in detail_rows
    )

    registry_html = ""
    if isinstance(registry_match, dict):
        business_items = registry_match.get("business_items") or []
        business_list = "".join(
            f"<li>{escape(str(item.get('description') or item.get('code') or '未提供'))}</li>"
            for item in business_items[:5]
            if isinstance(item, dict)
        )
        registry_html = f"""
        <div class="subsection">
          <h3>GCIS 公司正規化</h3>
          <div class="detail-row"><span>正式公司名</span><strong>{escape(str(registry_match.get('matched_name') or '未提供'))}</strong></div>
          <div class="detail-row"><span>統編</span><strong>{escape(str(registry_match.get('business_accounting_no') or '未提供'))}</strong></div>
          <div class="detail-row"><span>公司狀態</span><strong>{escape(str(registry_match.get('company_status') or '未提供'))}</strong></div>
          <div class="detail-row"><span>負責人</span><strong>{escape(str(registry_match.get('responsible_name') or '未提供'))}</strong></div>
          <div class="detail-row"><span>登記地址</span><strong>{escape(str(registry_match.get('company_location') or '未提供'))}</strong></div>
          <div class="detail-row"><span>資本額</span><strong>{escape(format_money(registry_match.get('capital_stock_amount')))}</strong></div>
          {f'<div class="business-items"><div class="label">營業項目</div><ul>{business_list}</ul></div>' if business_list else ''}
        </div>
        """
    elif isinstance(registry_meta, dict):
        meta = registry_meta.get("meta") or {}
        registry_html = f"""
        <div class="subsection muted">
          <h3>GCIS 公司正規化</h3>
          <p>{escape(str(meta.get('reason') or meta.get('status') or '未匹配'))}</p>
        </div>
        """

    maps_html = ""
    if isinstance(maps_match, dict):
        maps_html = f"""
        <div class="subsection">
          <h3>Google Maps</h3>
          <div class="detail-row"><span>名稱</span><strong>{escape(str(maps_match.get('name') or '未提供'))}</strong></div>
          <div class="detail-row"><span>地址</span><strong>{escape(str(maps_match.get('formatted_address') or '未提供'))}</strong></div>
          <div class="detail-row"><span>Place ID</span><strong>{escape(str(maps_match.get('place_id') or '未提供'))}</strong></div>
        </div>
        """

    tracking_status_options = "".join(
        f"<option value=\"{html_attr(option)}\">{escape(option)}</option>"
        for option in TRACKER_STATUS_OPTIONS
    )
    search_blob = " ".join(
        str(value or "")
        for value in (
            result.get("project_name"),
            result.get("developer_name"),
            result.get("site_address"),
            result.get("permit_number"),
            result.get("usage"),
            registry_match.get("matched_name") if isinstance(registry_match, dict) else "",
            registry_match.get("business_accounting_no")
            if isinstance(registry_match, dict)
            else "",
        )
    ).lower()
    lead_id = str(result.get("lead_id") or make_lead_id(result))

    return f"""
    <article
      class="result-card"
      data-lead-id="{html_attr(lead_id)}"
      data-source="{html_attr(result.get('source_tag') or '未知來源')}"
      data-search="{html_attr(search_blob)}"
      data-default-status="未處理"
    >
      <div class="card-top">
        <span class="source-pill">{escape(str(result.get('source_tag') or '未知來源'))}</span>
        <span class="budget-pill">{escape(format_money(result.get('construction_cost')))}</span>
      </div>
      <h2>{escape(str(result.get('project_name') or '未命名建案'))}</h2>
      <div class="lead-meta">Lead ID：{escape(lead_id)}</div>
      <div class="details-grid">{details_html}</div>
      {registry_html}
      {maps_html}
      <div class="subsection tracking-box">
        <div class="subsection-head">
          <h3>追蹤欄位</h3>
          <span class="tracking-pill js-tracking-pill">未處理</span>
        </div>
        <div class="tracking-grid">
          <label class="field">
            <span>狀態</span>
            <select class="js-track-status">
              <option value="">未處理</option>
              {tracking_status_options}
            </select>
          </label>
          <label class="field">
            <span>負責人</span>
            <input class="js-track-owner" type="text" placeholder="例如 Mandy">
          </label>
          <label class="field">
            <span>下次跟進</span>
            <input class="js-track-next-date" type="date">
          </label>
        </div>
        <label class="field">
          <span>備註</span>
          <textarea class="js-track-note" rows="3" placeholder="記錄聯絡窗口、需求、下一步"></textarea>
        </label>
        <p class="tracking-help">這些欄位會先存在你目前這台裝置的瀏覽器。若要多人共用，請下載 tracker.csv 丟到 Google Sheets 或之後再接共享資料庫。</p>
      </div>
    </article>
    """


def write_report_html(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sources = payload.get("sources", {})
    source_cards = "".join(
        render_source_card(str(name), data)
        for name, data in sources.items()
        if isinstance(data, dict)
    )
    results = payload.get("results", [])
    result_count = len([result for result in results if isinstance(result, dict)])
    result_cards = "".join(
        render_result_card(result)
        for result in results
        if isinstance(result, dict)
    ) or '<div class="empty-state">這次沒有可顯示的名單結果。</div>'

    status = str(payload.get("status") or "unknown")
    filters = payload.get("filters", {})
    source_options = "".join(
        f"<option value=\"{html_attr(result.get('source_tag') or '')}\">{escape(str(result.get('source_tag') or '未知來源'))}</option>"
        for result in {
            str(item.get("source_tag") or ""): item
            for item in results
            if isinstance(item, dict)
        }.values()
    )
    tracker_download_name = Path(str(payload.get("tracker_path") or "tracker.csv")).name
    report_data_json = json.dumps(results, ensure_ascii=False).replace("</", "<\\/")
    report_html = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weekly Crawl Report</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --panel: rgba(255,255,255,0.86);
      --ink: #1f2a1f;
      --muted: #5b6659;
      --line: rgba(31,42,31,0.10);
      --accent: #c86b29;
      --accent-soft: #f2d5bf;
      --olive: #53624a;
      --shadow: 0 18px 50px rgba(76, 63, 45, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "PingFang TC", "Noto Sans TC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(200,107,41,0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(83,98,74,0.16), transparent 30%),
        linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
    }}
    .wrap {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0 72px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(255,248,240,0.88));
      border: 1px solid rgba(200,107,41,0.14);
      border-radius: 28px;
      padding: 28px;
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -40px -60px auto;
      width: 220px;
      height: 220px;
      background: radial-gradient(circle, rgba(200,107,41,0.24), transparent 70%);
      pointer-events: none;
    }}
    .eyebrow {{
      display: inline-block;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 14px 0 8px;
      font-size: clamp(30px, 4vw, 52px);
      line-height: 0.98;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 760px;
      font-size: 16px;
      line-height: 1.6;
    }}
    .summary-grid, .source-grid, .results-grid {{
      display: grid;
      gap: 16px;
    }}
    .toolbar, .toolbar-actions, .toolbar-filters {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .toolbar {{
      margin-top: 20px;
      justify-content: space-between;
    }}
    .summary-grid {{
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      margin-top: 24px;
    }}
    .summary-card, .source-card, .result-card, .filter-panel {{
      background: var(--panel);
      backdrop-filter: blur(10px);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }}
    .summary-card {{
      padding: 20px;
    }}
    .summary-card .label {{
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .summary-card strong {{
      display: block;
      margin-top: 8px;
      font-size: 28px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin: 28px 0 14px;
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 24px;
    }}
    .section-head p {{
      margin: 4px 0 0;
      color: var(--muted);
    }}
    .source-grid {{
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }}
    .source-card, .filter-panel {{
      padding: 18px 20px;
    }}
    .source-name {{
      font-size: 18px;
      font-weight: 700;
    }}
    .source-url {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
      word-break: break-all;
    }}
    .source-meta {{
      margin-top: 12px;
      font-size: 14px;
      line-height: 1.6;
    }}
    .filter-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }}
    .toolbar input[type="search"],
    .toolbar select,
    .toolbar input[type="text"],
    .toolbar input[type="date"],
    .toolbar textarea {{
      width: 100%;
      border: 1px solid rgba(31,42,31,0.12);
      background: rgba(255,255,255,0.92);
      color: var(--ink);
      border-radius: 14px;
      padding: 12px 14px;
      font: inherit;
    }}
    .toolbar input[type="search"] {{
      min-width: min(320px, 100%);
    }}
    .toolbar select {{
      min-width: 160px;
    }}
    .ghost-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 46px;
      border: 1px solid rgba(31,42,31,0.12);
      border-radius: 14px;
      padding: 0 16px;
      text-decoration: none;
      font: inherit;
      color: var(--ink);
      background: rgba(255,255,255,0.82);
      cursor: pointer;
    }}
    .ghost-button:hover {{
      background: rgba(255,255,255,0.96);
    }}
    .filter-chip {{
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(83,98,74,0.08);
      color: var(--olive);
      font-size: 14px;
    }}
    .note-panel {{
      margin-top: 18px;
      padding: 16px 18px;
      border-radius: 18px;
      background: rgba(200,107,41,0.08);
      color: var(--ink);
      line-height: 1.6;
      border: 1px solid rgba(200,107,41,0.14);
    }}
    .results-grid {{
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    }}
    .result-card {{
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .source-pill, .budget-pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 700;
    }}
    .source-pill {{
      background: rgba(83,98,74,0.12);
      color: var(--olive);
    }}
    .budget-pill {{
      background: rgba(200,107,41,0.12);
      color: var(--accent);
    }}
    .result-card h2 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.15;
    }}
    .lead-meta {{
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }}
    .details-grid {{
      display: grid;
      gap: 10px;
    }}
    .detail-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      border-bottom: 1px dashed rgba(31,42,31,0.08);
      padding-bottom: 8px;
    }}
    .detail-row span {{
      color: var(--muted);
      min-width: 76px;
    }}
    .detail-row strong {{
      text-align: right;
      font-weight: 600;
      word-break: break-word;
    }}
    .subsection {{
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(83,98,74,0.05);
    }}
    .subsection h3 {{
      margin: 0 0 10px;
      font-size: 15px;
    }}
    .subsection-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .subsection.muted {{
      color: var(--muted);
    }}
    .tracking-box {{
      background: rgba(200,107,41,0.06);
    }}
    .tracking-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 12px;
    }}
    .field {{
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }}
    .field span {{
      font-weight: 600;
    }}
    .tracking-pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      background: rgba(83,98,74,0.12);
      color: var(--olive);
      font-size: 12px;
      font-weight: 700;
    }}
    .tracking-help {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    .utility-line {{
      color: var(--muted);
      font-size: 14px;
    }}
    .hidden {{
      display: none !important;
    }}
    .business-items .label {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }}
    .business-items ul {{
      margin: 8px 0 0 18px;
      padding: 0;
      line-height: 1.6;
    }}
    .empty-state {{
      padding: 24px;
      border-radius: 22px;
      background: var(--panel);
      border: 1px dashed var(--line);
      color: var(--muted);
      text-align: center;
    }}
    footer {{
      margin-top: 26px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }}
    @media (max-width: 720px) {{
      .wrap {{
        width: min(100vw - 20px, 1180px);
        padding-top: 20px;
      }}
      .hero, .summary-card, .source-card, .result-card, .filter-panel {{
        border-radius: 18px;
      }}
      .detail-row {{
        flex-direction: column;
      }}
      .detail-row strong {{
        text-align: left;
      }}
      .toolbar {{
        align-items: stretch;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <span class="eyebrow">Crawler Report</span>
      <h1>建案名單總覽</h1>
      <p class="subtitle">這份頁面會隨每次 crawler 執行自動更新，整合來源抓取狀態、篩選條件，以及目前可直接交給團隊看的名單內容。</p>
      <div class="summary-grid">
        <div class="summary-card"><div class="label">執行狀態</div><strong>{escape(status)}</strong></div>
        <div class="summary-card"><div class="label">原始資料</div><strong>{escape(format_count(payload.get('raw_record_count', 0)))}</strong></div>
        <div class="summary-card"><div class="label">符合條件</div><strong>{escape(format_count(payload.get('matched_record_count', 0)))}</strong></div>
        <div class="summary-card"><div class="label">GCIS 匹配</div><strong>{escape(format_count((payload.get('gcis_company_registry') or {}).get('matches_found', 0)))}</strong></div>
      </div>
      <div class="toolbar">
        <div class="toolbar-filters">
          <input id="searchInput" type="search" placeholder="搜尋建案、起造人、地址、統編">
          <select id="sourceFilter">
            <option value="">全部來源</option>
            {source_options}
          </select>
          <select id="trackingFilter">
            <option value="">全部追蹤狀態</option>
            <option value="未處理">未處理</option>
            <option value="待分派">待分派</option>
            <option value="待聯絡">待聯絡</option>
            <option value="聯絡中">聯絡中</option>
            <option value="已回覆">已回覆</option>
            <option value="已成交">已成交</option>
            <option value="已排除">已排除</option>
          </select>
        </div>
        <div class="toolbar-actions">
          <a class="ghost-button" href="./{html_attr(tracker_download_name)}" download>下載 tracker.csv</a>
          <button class="ghost-button" id="exportTrackingJson" type="button">匯出我的追蹤 JSON</button>
          <button class="ghost-button" id="exportTrackingCsv" type="button">匯出含追蹤 CSV</button>
        </div>
      </div>
      <div class="note-panel">
        這份頁面適合拿來分享給團隊看名單；若今天就要多人共用追蹤紀錄，最實用的做法是下載 <strong>tracker.csv</strong> 丟到 Google Sheets。頁面上的追蹤欄位也能先幫每位同事保留自己的進度。
      </div>
    </section>

    <div class="section-head">
      <div>
        <h2>來源狀態</h2>
        <p>快速檢查哪個來源今天有回資料，哪個來源仍然不穩。</p>
      </div>
    </div>
    <section class="source-grid">{source_cards}</section>

    <div class="section-head">
      <div>
        <h2>篩選條件</h2>
        <p>目前這次報表使用的條件設定。</p>
      </div>
    </div>
    <section class="filter-panel">
      <div class="filter-grid">
        <div class="filter-chip">起始日期：{escape(str(filters.get('start_date') or '未提供'))}</div>
        <div class="filter-chip">結束日期：{escape(str(filters.get('end_date') or '未提供'))}</div>
        <div class="filter-chip">最低造價：{escape(format_money(filters.get('min_construction_cost')))}</div>
        <div class="filter-chip">最多顯示：{escape(format_count(filters.get('max_projects') or 0))}</div>
        <div class="filter-chip">用途關鍵字：{escape(', '.join(filters.get('target_usages') or []) or '不限')}</div>
      </div>
    </section>

    <div class="section-head">
      <div>
        <h2>名單結果</h2>
        <p>優先顯示已符合篩選條件的案件，GCIS 與 Google Maps 會在可用時補強。</p>
      </div>
      <div class="utility-line">目前顯示 <strong id="visibleCount">{escape(format_count(result_count))}</strong> / {escape(format_count(result_count))} 筆</div>
    </div>
    <section class="results-grid">{result_cards}</section>

    <footer>
      產出時間：{escape(str(payload.get('finished_at') or payload.get('started_at') or '未提供'))}
    </footer>
  </div>
  <script id="reportData" type="application/json">{report_data_json}</script>
  <script>
    const TRACKING_PREFIX = "crawler-tracking:";
    const reportData = JSON.parse(document.getElementById("reportData").textContent || "[]");
    const cards = Array.from(document.querySelectorAll(".result-card"));
    const searchInput = document.getElementById("searchInput");
    const sourceFilter = document.getElementById("sourceFilter");
    const trackingFilter = document.getElementById("trackingFilter");
    const visibleCount = document.getElementById("visibleCount");

    function trackingKey(leadId) {{
      return TRACKING_PREFIX + leadId;
    }}

    function normalizeTracking(card) {{
      const leadId = card.dataset.leadId;
      let saved = {{}};
      try {{
        saved = JSON.parse(localStorage.getItem(trackingKey(leadId)) || "{{}}");
      }} catch (error) {{
        saved = {{}};
      }}
      const status = saved.status || card.dataset.defaultStatus || "未處理";
      const owner = saved.owner || "";
      const nextDate = saved.nextDate || "";
      const note = saved.note || "";

      card.querySelector(".js-track-status").value = status === "未處理" ? "" : status;
      card.querySelector(".js-track-owner").value = owner;
      card.querySelector(".js-track-next-date").value = nextDate;
      card.querySelector(".js-track-note").value = note;
      card.querySelector(".js-tracking-pill").textContent = status;
      card.dataset.trackingStatus = status;
      card.dataset.trackingOwner = owner.toLowerCase();
    }}

    function persistTracking(card) {{
      const leadId = card.dataset.leadId;
      const payload = {{
        status: card.querySelector(".js-track-status").value || "未處理",
        owner: card.querySelector(".js-track-owner").value.trim(),
        nextDate: card.querySelector(".js-track-next-date").value,
        note: card.querySelector(".js-track-note").value.trim()
      }};
      localStorage.setItem(trackingKey(leadId), JSON.stringify(payload));
      card.querySelector(".js-tracking-pill").textContent = payload.status;
      card.dataset.trackingStatus = payload.status;
      card.dataset.trackingOwner = payload.owner.toLowerCase();
      applyFilters();
    }}

    function applyFilters() {{
      const keyword = (searchInput.value || "").trim().toLowerCase();
      const source = sourceFilter.value;
      const trackingStatus = trackingFilter.value;
      let shown = 0;

      cards.forEach((card) => {{
        const matchesKeyword = !keyword || (card.dataset.search || "").includes(keyword) || (card.dataset.trackingOwner || "").includes(keyword);
        const matchesSource = !source || card.dataset.source === source;
        const matchesTracking = !trackingStatus || (card.dataset.trackingStatus || "未處理") === trackingStatus;
        const shouldShow = matchesKeyword && matchesSource && matchesTracking;
        card.classList.toggle("hidden", !shouldShow);
        if (shouldShow) {{
          shown += 1;
        }}
      }});

      visibleCount.textContent = shown.toLocaleString("zh-Hant-TW");
    }}

    function csvEscape(value) {{
      const text = String(value ?? "");
      if (/[",\\n]/.test(text)) {{
        return '"' + text.replace(/"/g, '""') + '"';
      }}
      return text;
    }}

    function readTracking(leadId) {{
      try {{
        return JSON.parse(localStorage.getItem(trackingKey(leadId)) || "{{}}");
      }} catch (error) {{
        return {{}};
      }}
    }}

    function downloadBlob(content, fileName, type) {{
      const blob = new Blob([content], {{ type }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      link.click();
      URL.revokeObjectURL(url);
    }}

    document.getElementById("exportTrackingJson").addEventListener("click", () => {{
      const payload = reportData.map((item) => {{
        const leadId = item.lead_id || "";
        return {{
          lead_id: leadId,
          project_name: item.project_name || "",
          developer_name: item.developer_name || "",
          source_tag: item.source_tag || "",
          permit_number: item.permit_number || "",
          tracking: readTracking(leadId)
        }};
      }});
      downloadBlob(JSON.stringify(payload, null, 2), "tracking-export.json", "application/json");
    }});

    document.getElementById("exportTrackingCsv").addEventListener("click", () => {{
      const header = [
        "lead_id",
        "source_tag",
        "project_name",
        "developer_name",
        "site_address",
        "permit_number",
        "permit_issued_at",
        "construction_cost",
        "usage",
        "tracking_status",
        "owner",
        "next_action_date",
        "note"
      ];
      const rows = [header.join(",")];
      reportData.forEach((item) => {{
        const tracking = readTracking(item.lead_id || "");
        rows.push([
          item.lead_id || "",
          item.source_tag || "",
          item.project_name || "",
          item.developer_name || "",
          item.site_address || "",
          item.permit_number || "",
          item.permit_issued_at || "",
          item.construction_cost || "",
          item.usage || "",
          tracking.status || "未處理",
          tracking.owner || "",
          tracking.nextDate || "",
          tracking.note || ""
        ].map(csvEscape).join(","));
      }});
      downloadBlob("\\ufeff" + rows.join("\\n"), "tracking-export.csv", "text/csv;charset=utf-8");
    }});

    cards.forEach((card) => {{
      normalizeTracking(card);
      card.querySelectorAll(".js-track-status, .js-track-owner, .js-track-next-date, .js-track-note").forEach((field) => {{
        field.addEventListener("change", () => persistTracking(card));
        field.addEventListener("input", () => persistTracking(card));
      }});
    }});

    [searchInput, sourceFilter, trackingFilter].forEach((field) => {{
      field.addEventListener("input", applyFilters);
      field.addEventListener("change", applyFilters);
    }});

    applyFilters();
  </script>
</body>
</html>
"""
    output_path.write_text(report_html, encoding="utf-8")
    print(f"Wrote crawler report to: {output_path}")


def write_report(report_path: str, payload: dict[str, Any]) -> None:
    write_report_html(Path(report_path), payload)
    index_path = str(payload.get("index_path") or "")
    if index_path:
        write_report_html(Path(index_path), payload)
    alias_path = str(payload.get("report_alias_path") or "")
    if alias_path:
        write_report_html(Path(alias_path), payload)


def write_tracker_csv(tracker_path: str, payload: dict[str, Any]) -> None:
    output_path = Path(tracker_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "lead_id",
        "source_tag",
        "region",
        "project_name",
        "developer_name",
        "architect_name",
        "site_address",
        "permit_number",
        "permit_issued_at",
        "construction_cost",
        "usage",
        "gcis_company_name",
        "gcis_business_no",
        "tracking_status",
        "owner",
        "next_action_date",
        "note",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in payload.get("results", []):
            if not isinstance(result, dict):
                continue
            registry_match = (
                result.get("gcis_company_registry", {}).get("match")
                if isinstance(result.get("gcis_company_registry"), dict)
                else None
            )
            writer.writerow(
                {
                    "lead_id": result.get("lead_id") or "",
                    "source_tag": result.get("source_tag") or "",
                    "region": result.get("region") or "",
                    "project_name": result.get("project_name") or "",
                    "developer_name": result.get("developer_name") or "",
                    "architect_name": result.get("architect_name") or "",
                    "site_address": result.get("site_address") or "",
                    "permit_number": result.get("permit_number") or "",
                    "permit_issued_at": result.get("permit_issued_at") or "",
                    "construction_cost": result.get("construction_cost") or 0,
                    "usage": result.get("usage") or "",
                    "gcis_company_name": (
                        registry_match.get("matched_name") if isinstance(registry_match, dict) else ""
                    ),
                    "gcis_business_no": (
                        registry_match.get("business_accounting_no")
                        if isinstance(registry_match, dict)
                        else ""
                    ),
                    "tracking_status": "未處理",
                    "owner": "",
                    "next_action_date": "",
                    "note": "",
                }
            )
    print(f"Wrote tracker CSV to: {output_path}")


def write_outputs(
    results_path: str,
    report_path: str,
    payload: dict[str, Any],
    shared_app_config: dict[str, Any],
) -> None:
    write_results(results_path, payload)
    write_report(report_path, payload)
    tracker_path = str(payload.get("tracker_path") or "")
    if tracker_path:
        write_tracker_csv(tracker_path, payload)
    site_output_dir = str(shared_app_config.get("site_output_dir") or "")
    if site_output_dir:
        write_secure_site(site_output_dir, payload, shared_app_config)


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
    if raw.isdigit() and len(raw) == 7:
        try:
            return date(int(raw[:3]) + 1911, int(raw[3:5]), int(raw[5:7])).isoformat()
        except ValueError:
            pass
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


def clean_company_query(name: str) -> str:
    candidate = name.strip()
    if not candidate or candidate == "待補":
        return ""
    for marker in ("負責人：", "負責人:", "代表人：", "代表人:", "校長：", "校長:"):
        candidate = candidate.split(marker, 1)[0].strip()
    for separator in ("，", ",", "；", ";", "\n"):
        candidate = candidate.split(separator, 1)[0].strip()
    candidate = candidate.replace("（", "(").replace("）", ")")
    return " ".join(candidate.split())


def normalize_company_name_for_compare(name: str) -> str:
    normalized = clean_company_query(name)
    for token in ("股份有限公司", "有限公司", "公司", "股份", " "):
        normalized = normalized.replace(token, "")
    return normalized


def should_lookup_gcis_company(name: str) -> bool:
    query = clean_company_query(name)
    if len(query) < 3:
        return False
    if any(hint in query for hint in COMPANY_NAME_HINTS):
        return True
    if "Ｏ" in query or "○" in query:
        return False
    return False


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


def parse_taipei_xml_records(xml_text: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"invalid_xml: {exc}") from exc

    records: list[dict[str, Any]] = []
    for data_node in root.findall(".//Data"):
        record: dict[str, Any] = {}
        for child in data_node:
            tag = child.tag.strip()
            if tag == "建築地點":
                record[tag] = [
                    (address.text or "").strip()
                    for address in child.findall(".//地址")
                    if (address.text or "").strip()
                ]
            elif tag == "地段地號":
                record[tag] = [
                    (land.text or "").strip()
                    for land in child.findall(".//地段號")
                    if (land.text or "").strip()
                ]
            elif tag == "建築概要":
                record[tag] = [
                    (floor.text or "").strip()
                    for floor in child.findall(".//樓層")
                    if (floor.text or "").strip()
                ]
            elif len(child):
                record[tag] = [
                    (nested.text or "").strip()
                    for nested in child
                    if (nested.text or "").strip()
                ]
            else:
                record[tag] = (child.text or "").strip()
        records.append(record)
    return records


def fetch_taipei_records(
    history_url: str,
    current_url: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resources = [
        ("history", history_url),
        ("current", current_url),
    ]
    combined_records: list[dict[str, Any]] = []
    resource_meta: list[dict[str, Any]] = []

    for label, url in resources:
        print(f"[台北市] 抓取 {label}: {url}")
        try:
            response = requests.get(
                url,
                headers={"Accept": "application/xml,text/xml,*/*"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"[台北市] {label} 抓取失敗: {exc}")
            return combined_records, {
                "status": "request_error",
                "error": str(exc),
                "resource": label,
                "record_count": len(combined_records),
                "resources": resource_meta,
            }

        xml_text = response.content.decode("utf-8-sig", errors="ignore")
        try:
            page_records = parse_taipei_xml_records(xml_text)
        except ValueError as exc:
            print(f"[台北市] {label} XML 解析失敗: {exc}")
            return combined_records, {
                "status": "invalid_xml",
                "error": str(exc),
                "resource": label,
                "http_status": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "body_preview": xml_text[:500],
                "record_count": len(combined_records),
                "resources": resource_meta,
            }

        combined_records.extend(page_records)
        resource_meta.append(
            {
                "name": label,
                "url": url,
                "status": "ok",
                "record_count": len(page_records),
            }
        )
        print(f"[台北市] {label} 取得 {len(page_records)} 筆")

    print(f"[台北市] 合計 {len(combined_records)} 筆原始資料")
    return combined_records, {
        "status": "ok",
        "record_count": len(combined_records),
        "resources": resource_meta,
    }


def collapse_location_values(values: list[str], limit: int = 3) -> str:
    unique_values: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in unique_values:
            unique_values.append(cleaned)
    if not unique_values:
        return ""
    if len(unique_values) <= limit:
        return " / ".join(unique_values)
    return f"{' / '.join(unique_values[:limit])} 等{len(unique_values)}處"


def extract_taipei_usage(usage_lines: list[str]) -> str:
    usages: list[str] = []
    for line in usage_lines:
        if "用途:" not in line:
            continue
        usage = line.split("用途:", 1)[1].strip()
        usage = re.sub(r"[（(][^）)]*[）)]", "", usage)
        parts = re.split(r"[、/；;,]", usage)
        for part in parts:
            cleaned = part.strip()
            cleaned = re.sub(r"[0-9]+(?:\.[0-9]+)?", "", cleaned)
            cleaned = cleaned.replace("㎡", "").replace("M", "").replace("m", "")
            cleaned = cleaned.replace(":", "").replace("：", "")
            cleaned = re.sub(r"\s+", "", cleaned)
            cleaned = cleaned.strip("。．-")
            cleaned = cleaned.split("依", 1)[0].strip() or cleaned
            if len(cleaned) > 18:
                cleaned = cleaned[:18]
            if len(cleaned) < 2:
                continue
            if cleaned not in usages:
                usages.append(cleaned)
    return " / ".join(usages[:10])


def normalize_taipei_permit(record: dict[str, Any]) -> dict[str, Any]:
    site_addresses = record.get("建築地點")
    if not isinstance(site_addresses, list):
        site_addresses = []
    land_numbers = record.get("地段地號")
    if not isinstance(land_numbers, list):
        land_numbers = []
    usage_lines = record.get("建築概要")
    if not isinstance(usage_lines, list):
        usage_lines = []

    site_address = collapse_location_values(site_addresses)
    if not site_address and land_numbers:
        site_address = collapse_location_values(land_numbers, limit=2)
    site_address = site_address or "地址待補齊"

    usage = extract_taipei_usage(usage_lines)
    permit_number = str(record.get("執照號碼") or "unknown").strip()
    project_name = site_address if site_address != "地址待補齊" else permit_number

    return {
        "permit_number": permit_number,
        "project_name": project_name,
        "developer_name": str(record.get("起造人") or "待補").strip(),
        "architect_name": str(record.get("設計人") or "").strip(),
        "site_address": site_address,
        "construction_cost": parse_number(record.get("工程金額") or 0),
        "permit_issued_at": normalize_date(record.get("發照日期") or ""),
        "usage": usage,
        "region": "台北市",
        "source_tag": "台北市",
        "land_use_zoning": str(record.get("使用分區") or "").strip(),
        "constructor_name": str(record.get("監造人") or "").strip(),
    }


def search_gcis_company_candidates(
    query: str,
    keyword_api_url: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "$format": "json",
        "$top": "5",
        "$filter": f"Company_Name like {query} and Company_Status eq 01",
    }
    try:
        response = requests.get(
            keyword_api_url,
            params=params,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return [], {"status": "request_error", "error": str(exc), "request_params": params}

    try:
        payload = response.json()
    except ValueError as exc:
        if not response.text.strip():
            return [], {
                "status": "empty_response",
                "http_status": response.status_code,
                "request_params": params,
            }
        return [], {
            "status": "invalid_json",
            "error": str(exc),
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "body_preview": response.text[:500],
            "request_params": params,
        }

    if not isinstance(payload, list):
        return [], {
            "status": "unexpected_payload",
            "http_status": response.status_code,
            "request_params": params,
        }
    candidates = [item for item in payload if isinstance(item, dict)]
    return candidates, {
        "status": "ok",
        "http_status": response.status_code,
        "record_count": len(candidates),
        "request_params": params,
    }


def score_gcis_candidate(query: str, candidate_name: str) -> tuple[int, int]:
    normalized_query = normalize_company_name_for_compare(query)
    normalized_candidate = normalize_company_name_for_compare(candidate_name)
    if not normalized_query or not normalized_candidate:
        return (0, 9999)
    if normalized_candidate == normalized_query:
        return (100, abs(len(candidate_name) - len(query)))
    if candidate_name == query:
        return (95, abs(len(candidate_name) - len(query)))
    if normalized_query in normalized_candidate:
        return (85, abs(len(candidate_name) - len(query)))
    if normalized_candidate in normalized_query:
        return (80, abs(len(candidate_name) - len(query)))
    return (0, 9999)


def fetch_gcis_company_details(
    business_accounting_no: str,
    details_api_url: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    params = {
        "$format": "json",
        "$top": "1",
        "$filter": f"Business_Accounting_NO eq {business_accounting_no}",
    }
    try:
        response = requests.get(
            details_api_url,
            params=params,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return None, {"status": "request_error", "error": str(exc), "request_params": params}

    try:
        payload = response.json()
    except ValueError as exc:
        return None, {
            "status": "invalid_json",
            "error": str(exc),
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "body_preview": response.text[:500],
            "request_params": params,
        }

    if not isinstance(payload, list) or not payload:
        return None, {
            "status": "no_results",
            "http_status": response.status_code,
            "request_params": params,
        }
    first = payload[0]
    if not isinstance(first, dict):
        return None, {
            "status": "unexpected_payload",
            "http_status": response.status_code,
            "request_params": params,
        }
    return first, {
        "status": "ok",
        "http_status": response.status_code,
        "request_params": params,
    }


def enrich_company_with_gcis(
    company_name: str,
    keyword_api_url: str,
    details_api_url: str,
    cache: dict[str, dict[str, Any] | None],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    query = clean_company_query(company_name)
    if not query:
        return None, {"status": "skipped", "reason": "empty_company_name"}
    if not should_lookup_gcis_company(query):
        return None, {"status": "skipped", "reason": "not_company_like", "query": query}
    if query in cache:
        cached = cache[query]
        status = "cache_hit_match" if cached else "cache_hit_no_match"
        return cached, {"status": status, "query": query}

    candidates, search_meta = search_gcis_company_candidates(query, keyword_api_url)
    if not candidates:
        cache[query] = None
        return None, {"status": "no_candidates", "query": query, "search": search_meta}

    scored_candidates = sorted(
        candidates,
        key=lambda candidate: score_gcis_candidate(
            query,
            str(candidate.get("Company_Name") or "").strip(),
        ),
        reverse=True,
    )
    best = scored_candidates[0]
    best_name = str(best.get("Company_Name") or "").strip()
    best_score, _ = score_gcis_candidate(query, best_name)
    if best_score <= 0:
        cache[query] = None
        return None, {
            "status": "no_confident_match",
            "query": query,
            "search": search_meta,
        }

    business_no = str(best.get("Business_Accounting_NO") or "").strip()
    details = None
    details_meta: dict[str, Any] = {"status": "skipped", "reason": "missing_business_no"}
    if business_no:
        details, details_meta = fetch_gcis_company_details(business_no, details_api_url)

    business_items: list[dict[str, str]] = []
    if details:
        raw_items = details.get("Cmp_Business")
        if isinstance(raw_items, list):
            for item in raw_items[:10]:
                if not isinstance(item, dict):
                    continue
                business_items.append(
                    {
                        "code": str(item.get("Business_Item") or "").strip(),
                        "description": str(item.get("Business_Item_Desc") or "").strip(),
                    }
                )

    company_status = str(best.get("Company_Status_Desc") or best.get("Company_Status") or "").strip()
    responsible_name = str(best.get("Responsible_Name") or "").strip()
    company_location = str(best.get("Company_Location") or "").strip()
    company_setup_date = normalize_date(best.get("Company_Setup_Date") or "")
    if details:
        company_status = company_status or str(
            details.get("Company_Status_Desc") or details.get("Company_Status") or ""
        ).strip()
        responsible_name = responsible_name or str(
            details.get("Responsible_Name") or ""
        ).strip()
        company_location = company_location or str(
            details.get("Company_Location") or ""
        ).strip()
        company_setup_date = company_setup_date or normalize_date(
            details.get("Company_Setup_Date") or ""
        )

    enriched = {
        "query": query,
        "matched_name": best_name,
        "business_accounting_no": business_no,
        "company_status": company_status,
        "responsible_name": responsible_name,
        "company_location": company_location,
        "company_setup_date": company_setup_date,
        "register_organization": str(best.get("Register_Organization_Desc") or "").strip(),
        "capital_stock_amount": parse_number(best.get("Capital_Stock_Amount") or 0),
        "paid_in_capital_amount": parse_number(best.get("Paid_In_Capital_Amount") or 0),
        "business_items": business_items,
    }
    cache[query] = enriched
    return enriched, {
        "status": "matched",
        "query": query,
        "search": search_meta,
        "details": details_meta,
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
    registry_data: dict[str, Any] | None,
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

    company_name = permit["developer_name"]
    if registry_data:
        normalized_name = str(registry_data.get("matched_name") or "").strip()
        if normalized_name:
            company_name = normalized_name

    record: dict[str, Any] = {
        "company_name": company_name,
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


def build_shared_lead_record(
    permit: dict[str, Any],
    finished_at: str,
) -> dict[str, Any]:
    registry_match = (
        permit.get("gcis_company_registry", {}).get("match")
        if isinstance(permit.get("gcis_company_registry"), dict)
        else None
    )
    maps_match = permit.get("google_maps_match")
    maps_url = None
    if isinstance(maps_match, dict):
        place_id = str(maps_match.get("place_id") or "").strip()
        if place_id:
            maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

    return {
        "lead_id": permit.get("lead_id") or make_lead_id(permit),
        "source_tag": permit.get("source_tag") or "",
        "region": permit.get("region") or "",
        "permit_number": permit.get("permit_number") or "",
        "project_name": permit.get("project_name") or "",
        "developer_name": permit.get("developer_name") or "",
        "architect_name": permit.get("architect_name") or "",
        "constructor_name": permit.get("constructor_name") or None,
        "site_address": permit.get("site_address") or "",
        "construction_cost": parse_number(permit.get("construction_cost")),
        "permit_issued_at": normalize_date(permit.get("permit_issued_at")) or None,
        "usage": permit.get("usage") or "",
        "land_use_zoning": permit.get("land_use_zoning") or None,
        "gcis_company_name": (
            registry_match.get("matched_name") if isinstance(registry_match, dict) else None
        ),
        "gcis_business_no": (
            registry_match.get("business_accounting_no")
            if isinstance(registry_match, dict)
            else None
        ),
        "gcis_company_status": (
            registry_match.get("company_status") if isinstance(registry_match, dict) else None
        ),
        "gcis_responsible_name": (
            registry_match.get("responsible_name")
            if isinstance(registry_match, dict)
            else None
        ),
        "gcis_company_location": (
            registry_match.get("company_location")
            if isinstance(registry_match, dict)
            else None
        ),
        "google_maps_name": (
            maps_match.get("name") if isinstance(maps_match, dict) else None
        ),
        "google_maps_address": (
            maps_match.get("formatted_address")
            if isinstance(maps_match, dict)
            else None
        ),
        "google_maps_place_id": (
            maps_match.get("place_id") if isinstance(maps_match, dict) else None
        ),
        "google_maps_url": maps_url,
        "last_crawled_at": finished_at,
    }


def upsert_shared_leads_to_supabase(
    supabase_url: str,
    service_key: str,
    table_name: str,
    permits: list[dict[str, Any]],
    finished_at: str,
) -> None:
    if not permits:
        return

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    records = [build_shared_lead_record(permit, finished_at) for permit in permits]
    chunk_size = 100
    success_count = 0

    for start in range(0, len(records), chunk_size):
        chunk = records[start : start + chunk_size]
        try:
            response = requests.post(
                f"{supabase_url}/rest/v1/{table_name}?on_conflict=lead_id",
                headers=headers,
                data=json.dumps(chunk),
                timeout=30,
            )
            if response.ok:
                success_count += len(chunk)
            else:
                print(
                    f"  ✗ Shared leads 寫入失敗 ({response.status_code}): "
                    f"{response.text[:200]}"
                )
        except requests.RequestException as exc:
            print(f"  ✗ Shared leads 連線錯誤: {exc}")

    if success_count:
        print(f"  ✓ Shared leads: 已同步 {success_count} 筆到 {table_name}")


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Crawler started at: {started_at}")
    load_environment()
    results_path = get_env("RESULTS_PATH", DEFAULT_RESULTS_PATH)
    report_path = get_env("REPORT_PATH", default_report_path(results_path))
    index_path = get_env("INDEX_PATH", default_index_path(results_path))
    tracker_path = get_env("TRACKER_PATH", default_tracker_path(results_path))
    site_output_dir = get_env("SITE_OUTPUT_DIR", DEFAULT_SITE_OUTPUT_DIR)

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    supabase_publishable_key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    supabase_ready = bool(supabase_url and supabase_key)
    allowed_email_domain = get_env(
        "SHARED_APP_ALLOWED_EMAIL_DOMAIN", DEFAULT_ALLOWED_EMAIL_DOMAIN
    ).lstrip("@")
    shared_app_table = get_env("SHARED_APP_TABLE", DEFAULT_SHARED_APP_TABLE)

    if supabase_ready:
        print("✓ Supabase 設定確認，資料將寫入 leads 表。")
    else:
        print("⚠ Supabase 未設定，資料只會 print。")
    if supabase_publishable_key:
        print(f"✓ 內部頁面已設定登入金鑰，將限制 @{allowed_email_domain}。")
    else:
        print("⚠ 尚未設定 SUPABASE_PUBLISHABLE_KEY，內部登入頁只會顯示設定提示。")

    start_date = get_env("PERMIT_START_DATE", "2023-01-01")
    end_date = get_env("PERMIT_END_DATE", datetime.now(timezone.utc).date().isoformat())
    min_cost = parse_int_env("MIN_CONSTRUCTION_COST", DEFAULT_MIN_CONSTRUCTION_COST)
    max_projects = parse_int_env("MAX_PROJECTS", DEFAULT_MAX_PROJECTS)
    target_usages = parse_list_env("TARGET_USAGES", DEFAULT_TARGET_USAGES)
    google_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    nlma_url = get_env("NLMA_BMLIC_API_URL", DEFAULT_NLMA_BMLIC_API_URL)
    gcis_lookup_enabled = parse_bool_env("GCIS_COMPANY_LOOKUP_ENABLED", True)
    gcis_keyword_api_url = get_env(
        "GCIS_COMPANY_KEYWORD_API_URL",
        DEFAULT_GCIS_COMPANY_KEYWORD_API_URL,
    )
    gcis_details_api_url = get_env(
        "GCIS_COMPANY_DETAILS_API_URL",
        DEFAULT_GCIS_COMPANY_DETAILS_API_URL,
    )
    new_taipei_url = get_env("NEW_TAIPEI_JSON_URL", DEFAULT_NEW_TAIPEI_JSON_URL)
    new_taipei_page_size = parse_int_env(
        "NEW_TAIPEI_PAGE_SIZE", DEFAULT_NEW_TAIPEI_PAGE_SIZE
    )
    new_taipei_max_pages = parse_int_env(
        "NEW_TAIPEI_MAX_PAGES", DEFAULT_NEW_TAIPEI_MAX_PAGES
    )
    taipei_history_url = get_env(
        "TAIPEI_HISTORY_XML_URL",
        DEFAULT_TAIPEI_HISTORY_XML_URL,
    )
    taipei_current_url = get_env(
        "TAIPEI_CURRENT_XML_URL",
        DEFAULT_TAIPEI_CURRENT_XML_URL,
    )
    report_alias_path = dated_report_path(report_path, start_date, end_date)
    shared_app_config = {
        "site_output_dir": site_output_dir,
        "supabase_url": supabase_url,
        "supabase_key": supabase_publishable_key,
        "allowedEmailDomain": allowed_email_domain,
        "sharedTable": shared_app_table,
        "maxProjects": max_projects,
        "report_alias_name": Path(report_alias_path).name,
    }

    results_payload: dict[str, Any] = {
        "started_at": started_at,
        "finished_at": None,
        "status": "running",
        "results_path": results_path,
        "report_path": report_path,
        "index_path": index_path,
        "tracker_path": tracker_path,
        "report_alias_path": report_alias_path,
        "site_output_dir": site_output_dir,
        "sources": {
            "nlma": {"url": nlma_url, "fetch": {}},
            "new_taipei": {
                "url": new_taipei_url,
                "page_size": new_taipei_page_size,
                "max_pages": new_taipei_max_pages,
                "fetch": {},
            },
            "taipei": {
                "history_url": taipei_history_url,
                "current_url": taipei_current_url,
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
            "publishable_key_configured": bool(supabase_publishable_key),
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
        "shared_app": {
            "site_output_dir": site_output_dir,
            "allowed_email_domain": allowed_email_domain,
            "table": shared_app_table,
            "publishable_key_configured": bool(supabase_publishable_key),
        },
        "gcis_company_registry": {
            "enabled": gcis_lookup_enabled,
            "keyword_api_url": gcis_keyword_api_url,
            "details_api_url": gcis_details_api_url,
            "lookups_attempted": 0,
            "matches_found": 0,
        },
        "raw_record_count": 0,
        "matched_record_count": 0,
        "results": [],
    }

    print(f"篩選條件: {start_date} ~ {end_date}, 最低造價={min_cost:,}, 最多={max_projects}")

    if not google_key:
        print("⚠ 未設定 GOOGLE_MAPS_API_KEY，跳過 Google Maps 補強。")
    if not gcis_lookup_enabled:
        print("⚠ 已停用 GCIS 公司名稱正規化。")

    all_permits: list[dict[str, Any]] = []
    gcis_cache: dict[str, dict[str, Any] | None] = {}

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

    taipei_raw, taipei_meta = fetch_taipei_records(
        taipei_history_url,
        taipei_current_url,
    )
    results_payload["sources"]["taipei"]["fetch"] = taipei_meta
    all_permits += [normalize_taipei_permit(record) for record in taipei_raw]

    taichung_raw, taichung_meta = fetch_taichung_records()
    results_payload["sources"]["taichung"]["fetch"] = taichung_meta
    all_permits += [normalize_taichung_permit(record) for record in taichung_raw]

    results_payload["raw_record_count"] = len(all_permits)
    print(f"\n合計原始資料: {len(all_permits)} 筆")

    if not all_permits:
        print("無任何原始資料。Exiting successfully.")
        results_payload["status"] = "no_source_records"
        results_payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_outputs(results_path, report_path, results_payload, shared_app_config)
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
        write_outputs(results_path, report_path, results_payload, shared_app_config)
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
        registry_data = None
        if gcis_lookup_enabled:
            results_payload["gcis_company_registry"]["lookups_attempted"] += 1
            registry_data, registry_meta = enrich_company_with_gcis(
                permit["developer_name"],
                gcis_keyword_api_url,
                gcis_details_api_url,
                gcis_cache,
            )
            result_permit["gcis_company_registry"] = {
                "match": registry_data,
                "meta": registry_meta,
            }
            if registry_data:
                results_payload["gcis_company_registry"]["matches_found"] += 1
                print(
                    "  GCIS: "
                    f"{registry_data['matched_name']} | 統編 {registry_data['business_accounting_no']}"
                )

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
            upsert_to_supabase(
                supabase_url,
                supabase_key,
                permit,
                maps_data,
                registry_data,
            )

        selected_results.append(result_permit)

    for result in selected_results:
        result["lead_id"] = make_lead_id(result)

    results_payload["results"] = selected_results
    results_payload["status"] = "completed"
    results_payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    if supabase_ready:
        upsert_shared_leads_to_supabase(
            supabase_url,
            supabase_key,
            shared_app_table,
            selected_results,
            str(results_payload["finished_at"]),
        )
    write_outputs(results_path, report_path, results_payload, shared_app_config)
    print("\nCrawler completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
