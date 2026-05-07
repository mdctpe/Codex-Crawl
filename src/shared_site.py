from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


def html_attr(value: Any) -> str:
    return escape(str(value), quote=True)


def format_count(value: Any) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def build_secure_site_html(payload: dict[str, Any], app_config: dict[str, Any]) -> str:
    summary = {
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "status": payload.get("status"),
        "raw_record_count": payload.get("raw_record_count", 0),
        "matched_record_count": payload.get("matched_record_count", 0),
        "filters": payload.get("filters", {}),
        "sources": payload.get("sources", {}),
    }
    config_json = json.dumps(app_config, ensure_ascii=False).replace("</", "<\\/")
    summary_json = json.dumps(summary, ensure_ascii=False).replace("</", "<\\/")
    html = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Eonian Internal Leads</title>
  <style>
    :root {
      --bg: #f4efe7;
      --panel: rgba(255,255,255,0.9);
      --ink: #1f2a1f;
      --muted: #5b6659;
      --line: rgba(31,42,31,0.10);
      --accent: #c86b29;
      --accent-soft: #f2d5bf;
      --olive: #53624a;
      --shadow: 0 18px 50px rgba(76, 63, 45, 0.10);
      --ok: #2f7d32;
      --warn: #a65f00;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "PingFang TC", "Noto Sans TC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(200,107,41,0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(83,98,74,0.16), transparent 30%),
        linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
    }
    .wrap {
      width: min(1240px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 72px;
    }
    .panel,
    .card,
    .source-card,
    .lead-card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }
    .hero {
      padding: 28px;
      position: relative;
      overflow: hidden;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -40px -60px auto;
      width: 220px;
      height: 220px;
      background: radial-gradient(circle, rgba(200,107,41,0.24), transparent 70%);
      pointer-events: none;
    }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    h1 {
      margin: 14px 0 8px;
      font-size: clamp(30px, 4vw, 50px);
      line-height: 0.98;
    }
    .subtitle {
      margin: 0;
      color: var(--muted);
      max-width: 780px;
      font-size: 16px;
      line-height: 1.6;
    }
    .summary-grid,
    .source-grid,
    .lead-grid,
    .filter-grid,
    .tracking-grid {
      display: grid;
      gap: 16px;
    }
    .summary-grid {
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      margin-top: 24px;
    }
    .card {
      padding: 20px;
    }
    .card .label {
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .card strong {
      display: block;
      margin-top: 8px;
      font-size: 28px;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin: 28px 0 14px;
    }
    .section-head h2 {
      margin: 0;
      font-size: 24px;
    }
    .section-head p {
      margin: 4px 0 0;
      color: var(--muted);
    }
    .source-grid {
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }
    .source-card,
    .login-panel,
    .filter-panel {
      padding: 18px 20px;
    }
    .toolbar,
    .toolbar-actions,
    .toolbar-filters,
    .session-row {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }
    .toolbar {
      justify-content: space-between;
      margin-top: 20px;
    }
    input[type="search"],
    input[type="email"],
    input[type="text"],
    input[type="date"],
    select,
    textarea,
    button {
      font: inherit;
    }
    input[type="search"],
    input[type="email"],
    input[type="text"],
    input[type="date"],
    select,
    textarea {
      width: 100%;
      border: 1px solid rgba(31,42,31,0.12);
      background: rgba(255,255,255,0.96);
      color: var(--ink);
      border-radius: 14px;
      padding: 12px 14px;
    }
    .toolbar input[type="search"] {
      min-width: min(320px, 100%);
    }
    .filter-grid {
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      margin-top: 12px;
    }
    .filter-chip {
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(83,98,74,0.08);
      color: var(--olive);
      font-size: 14px;
    }
    .button,
    .ghost-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 46px;
      border-radius: 14px;
      padding: 0 16px;
      cursor: pointer;
      text-decoration: none;
      border: 1px solid transparent;
    }
    .button {
      background: var(--accent);
      color: white;
    }
    .ghost-button {
      border-color: rgba(31,42,31,0.12);
      background: rgba(255,255,255,0.86);
      color: var(--ink);
    }
    .button:disabled,
    .ghost-button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .login-panel {
      margin-top: 18px;
      display: grid;
      gap: 14px;
      background: rgba(200,107,41,0.08);
      border: 1px solid rgba(200,107,41,0.14);
      border-radius: 18px;
    }
    .login-grid {
      display: grid;
      grid-template-columns: minmax(240px, 380px) auto;
      gap: 12px;
      align-items: center;
    }
    .session-row {
      justify-content: space-between;
      margin-top: 12px;
    }
    .status-line {
      font-size: 14px;
      color: var(--muted);
      line-height: 1.6;
    }
    .status-line.ok { color: var(--ok); }
    .status-line.warn { color: var(--warn); }
    .status-line.danger { color: var(--danger); }
    .lead-grid {
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }
    .lead-card {
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .card-top,
    .subsection-head,
    .detail-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }
    .source-pill,
    .budget-pill,
    .tracking-pill,
    .save-pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 12px;
      font-weight: 700;
    }
    .source-pill {
      background: rgba(83,98,74,0.12);
      color: var(--olive);
    }
    .budget-pill {
      background: rgba(200,107,41,0.12);
      color: var(--accent);
    }
    .tracking-pill {
      background: rgba(83,98,74,0.12);
      color: var(--olive);
      padding: 6px 10px;
    }
    .save-pill {
      background: rgba(83,98,74,0.10);
      color: var(--muted);
      padding: 6px 10px;
    }
    .save-pill.saving {
      background: rgba(200,107,41,0.14);
      color: var(--accent);
    }
    .save-pill.error {
      background: rgba(180,35,24,0.12);
      color: var(--danger);
    }
    .lead-card h3 {
      margin: 0;
      font-size: 24px;
      line-height: 1.15;
    }
    .lead-meta {
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }
    .details-grid {
      display: grid;
      gap: 10px;
    }
    .detail-row {
      border-bottom: 1px dashed rgba(31,42,31,0.08);
      padding-bottom: 8px;
    }
    .detail-row span {
      color: var(--muted);
      min-width: 76px;
    }
    .detail-row strong {
      text-align: right;
      font-weight: 600;
      word-break: break-word;
    }
    .subsection {
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(83,98,74,0.05);
    }
    .tracking-box {
      background: rgba(200,107,41,0.06);
    }
    .tracking-grid {
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      margin-bottom: 12px;
    }
    .field {
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }
    .field span {
      font-weight: 600;
    }
    .utility-line,
    .muted {
      color: var(--muted);
      font-size: 14px;
    }
    .empty-state {
      padding: 24px;
      border-radius: 22px;
      background: var(--panel);
      border: 1px dashed var(--line);
      color: var(--muted);
      text-align: center;
    }
    .hidden { display: none !important; }
    .business-items .label {
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }
    .business-items ul {
      margin: 8px 0 0 18px;
      padding: 0;
      line-height: 1.6;
    }
    a.inline-link { color: var(--accent); }
    @media (max-width: 720px) {
      .wrap {
        width: min(100vw - 20px, 1240px);
        padding-top: 20px;
      }
      .hero,
      .card,
      .source-card,
      .lead-card,
      .login-panel,
      .filter-panel {
        border-radius: 18px;
      }
      .detail-row {
        flex-direction: column;
      }
      .detail-row strong {
        text-align: left;
      }
      .login-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="panel hero">
      <span class="eyebrow">Eonian Internal</span>
      <h1>內部建案追蹤台</h1>
      <p class="subtitle">只有登入後才會從 Supabase 讀取名單與追蹤欄位。GitHub Pages 本身不再公開內文資料，追蹤狀態也會直接寫回共享資料庫。</p>

      <div class="summary-grid">
        <div class="card"><div class="label">這次抓取狀態</div><strong id="summaryStatus">-</strong></div>
        <div class="card"><div class="label">原始資料</div><strong id="summaryRaw">-</strong></div>
        <div class="card"><div class="label">符合條件</div><strong id="summaryMatched">-</strong></div>
        <div class="card"><div class="label">可追蹤名單</div><strong id="summaryVisible">0</strong></div>
      </div>

      <section class="login-panel">
        <div>
          <strong>登入限制</strong>
          <p class="muted">只接受 <span id="allowedDomainLabel">@eonian.space</span> 帳號登入。登入後才會顯示案場內容與保存編輯。</p>
        </div>
        <div class="login-grid">
          <input id="emailInput" type="email" placeholder="you@eonian.space">
          <button class="button" id="sendMagicLinkButton" type="button">寄送登入連結</button>
        </div>
        <div class="session-row">
          <div id="authMessage" class="status-line">尚未登入。</div>
          <button class="ghost-button hidden" id="signOutButton" type="button">登出</button>
        </div>
      </section>
    </section>

    <div class="section-head">
      <div>
        <h2>來源狀態</h2>
        <p>這裡只顯示 crawler 本次更新摘要；真正的名單內容必須登入後才會載入。</p>
      </div>
    </div>
    <section class="source-grid" id="sourceGrid"></section>

    <div class="section-head">
      <div>
        <h2>篩選條件</h2>
        <p>這份內部頁面會沿用本次 crawler 的條件設定。</p>
      </div>
    </div>
    <section class="panel filter-panel">
      <div class="filter-grid" id="filterChips"></div>
    </section>

    <div class="section-head">
      <div>
        <h2>共用名單</h2>
        <p>登入成功後，這裡會從 Supabase 讀出可追蹤案場，並把編輯直接寫回共享資料庫。</p>
      </div>
      <div class="utility-line" id="resultMeta">尚未載入</div>
    </div>

    <section class="panel filter-panel hidden" id="leadToolbar">
      <div class="toolbar">
        <div class="toolbar-filters">
          <input id="searchInput" type="search" placeholder="搜尋建案、起造人、地址、統編">
          <select id="sourceFilter"><option value="">全部來源</option></select>
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
          <input id="ownerFilter" type="search" placeholder="搜尋負責人">
        </div>
        <div class="toolbar-actions">
          <button class="ghost-button" id="refreshButton" type="button">重新整理</button>
        </div>
      </div>
    </section>

    <section class="lead-grid" id="leadGrid">
      <div class="empty-state">登入後即可查看內部案場名單。</div>
    </section>
  </div>

  <script type="module">
    import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

    const APP_CONFIG = __CONFIG_JSON__;
    const INITIAL_SUMMARY = __SUMMARY_JSON__;
    const TRACKING_STATUSES = ["未處理", "待分派", "待聯絡", "聯絡中", "已回覆", "已成交", "已排除"];

    const state = {
      supabase: null,
      session: null,
      rows: [],
      filteredRows: [],
      saveTimers: new Map(),
      saveStates: new Map(),
    };

    const elements = {
      allowedDomainLabel: document.getElementById("allowedDomainLabel"),
      emailInput: document.getElementById("emailInput"),
      sendMagicLinkButton: document.getElementById("sendMagicLinkButton"),
      authMessage: document.getElementById("authMessage"),
      signOutButton: document.getElementById("signOutButton"),
      sourceGrid: document.getElementById("sourceGrid"),
      filterChips: document.getElementById("filterChips"),
      summaryStatus: document.getElementById("summaryStatus"),
      summaryRaw: document.getElementById("summaryRaw"),
      summaryMatched: document.getElementById("summaryMatched"),
      summaryVisible: document.getElementById("summaryVisible"),
      resultMeta: document.getElementById("resultMeta"),
      leadGrid: document.getElementById("leadGrid"),
      leadToolbar: document.getElementById("leadToolbar"),
      searchInput: document.getElementById("searchInput"),
      sourceFilter: document.getElementById("sourceFilter"),
      trackingFilter: document.getElementById("trackingFilter"),
      ownerFilter: document.getElementById("ownerFilter"),
      refreshButton: document.getElementById("refreshButton"),
    };

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function htmlAttr(value) {
      return escapeHtml(value);
    }

    function formatCount(value) {
      const amount = Number(value || 0);
      return Number.isFinite(amount) ? amount.toLocaleString("zh-Hant-TW") : String(value ?? "");
    }

    function formatMoney(value) {
      const amount = Number(value || 0);
      if (!Number.isFinite(amount) || amount <= 0) {
        return "未提供";
      }
      return "NT$ " + amount.toLocaleString("zh-Hant-TW");
    }

    function formatDate(value) {
      return value ? String(value) : "未提供";
    }

    function isAllowedEmail(email) {
      const suffix = "@" + String(APP_CONFIG.allowedEmailDomain || "").toLowerCase();
      return email.toLowerCase().endsWith(suffix);
    }

    function setAuthMessage(text, tone = "") {
      elements.authMessage.textContent = text;
      elements.authMessage.className = "status-line" + (tone ? " " + tone : "");
    }

    function updateSummary() {
      elements.summaryStatus.textContent = INITIAL_SUMMARY.status || "-";
      elements.summaryRaw.textContent = formatCount(INITIAL_SUMMARY.raw_record_count);
      elements.summaryMatched.textContent = formatCount(INITIAL_SUMMARY.matched_record_count);
      elements.summaryVisible.textContent = formatCount(state.filteredRows.length);
    }

    function renderSourceCards() {
      const entries = Object.entries(INITIAL_SUMMARY.sources || {});
      elements.sourceGrid.innerHTML = entries.map(([name, meta]) => {
        const fetch = meta.fetch || {};
        const bits = ["狀態：" + escapeHtml(fetch.status || "unknown")];
        if (fetch.record_count !== undefined && fetch.record_count !== null) {
          bits.push("筆數：" + escapeHtml(formatCount(fetch.record_count)));
        }
        if (fetch.error) {
          bits.push("錯誤：" + escapeHtml(fetch.error));
        }
        const url = meta.url || meta.current_url || meta.history_url || "";
        return `
          <article class="source-card">
            <strong>${escapeHtml(name)}</strong>
            <div class="muted" style="margin-top:6px;word-break:break-all;">${escapeHtml(url)}</div>
            <div class="status-line" style="margin-top:12px;">${bits.join("<br>")}</div>
          </article>
        `;
      }).join("");
    }

    function renderFilterChips() {
      const filters = INITIAL_SUMMARY.filters || {};
      const chips = [
        ["起始日期", filters.start_date || "未提供"],
        ["結束日期", filters.end_date || "未提供"],
        ["最低造價", formatMoney(filters.min_construction_cost)],
        ["最多顯示", formatCount(filters.max_projects || 0)],
        ["用途關鍵字", (filters.target_usages || []).join(", ") || "不限"],
      ];
      elements.filterChips.innerHTML = chips.map(([label, value]) => (
        `<div class="filter-chip">${escapeHtml(label)}：${escapeHtml(value)}</div>`
      )).join("");
    }

    function saveStateClass(status) {
      if (status === "saving") return "save-pill saving";
      if (status === "error") return "save-pill error";
      return "save-pill";
    }

    function saveStateText(status) {
      if (status === "saving") return "儲存中";
      if (status === "saved") return "已儲存";
      if (status === "error") return "儲存失敗";
      return "待更新";
    }

    function cardSearchBlob(row) {
      return [
        row.project_name,
        row.developer_name,
        row.site_address,
        row.permit_number,
        row.usage,
        row.gcis_company_name,
        row.gcis_business_no,
        row.tracking_owner,
        row.tracking_note,
      ].join(" ").toLowerCase();
    }

    function renderLeadCard(row) {
      const trackingStatus = row.tracking_status || "未處理";
      const saveStatus = state.saveStates.get(row.lead_id) || "idle";
      const detailRows = [
        ["來源", row.source_tag || "未提供"],
        ["建案名稱", row.project_name || "未提供"],
        ["起造人", row.developer_name || "未提供"],
        ["建築師", row.architect_name || "未提供"],
        ["地址", row.site_address || "未提供"],
        ["造價", formatMoney(row.construction_cost)],
        ["用途", row.usage || "未提供"],
        ["發照日期", formatDate(row.permit_issued_at)],
        ["執照字號", row.permit_number || "未提供"],
      ];
      if (row.land_use_zoning) {
        detailRows.push(["使用分區", row.land_use_zoning]);
      }
      if (row.constructor_name) {
        detailRows.push(["承造人", row.constructor_name]);
      }
      const detailsHtml = detailRows.map(([label, value]) => `
        <div class="detail-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>
      `).join("");

      let registryHtml = "";
      if (row.gcis_company_name || row.gcis_business_no) {
        registryHtml = `
          <div class="subsection">
            <h4 style="margin:0 0 10px;">GCIS 公司正規化</h4>
            <div class="detail-row"><span>正式公司名</span><strong>${escapeHtml(row.gcis_company_name || "未提供")}</strong></div>
            <div class="detail-row"><span>統編</span><strong>${escapeHtml(row.gcis_business_no || "未提供")}</strong></div>
            <div class="detail-row"><span>公司狀態</span><strong>${escapeHtml(row.gcis_company_status || "未提供")}</strong></div>
            <div class="detail-row"><span>負責人</span><strong>${escapeHtml(row.gcis_responsible_name || "未提供")}</strong></div>
            <div class="detail-row"><span>登記地址</span><strong>${escapeHtml(row.gcis_company_location || "未提供")}</strong></div>
          </div>
        `;
      }

      let mapsHtml = "";
      if (row.google_maps_name || row.google_maps_address || row.google_maps_place_id) {
        const mapsLink = row.google_maps_url
          ? `<a class="inline-link" href="${htmlAttr(row.google_maps_url)}" target="_blank" rel="noreferrer">打開 Google Maps</a>`
          : "";
        mapsHtml = `
          <div class="subsection">
            <h4 style="margin:0 0 10px;">Google Maps</h4>
            <div class="detail-row"><span>名稱</span><strong>${escapeHtml(row.google_maps_name || "未提供")}</strong></div>
            <div class="detail-row"><span>地址</span><strong>${escapeHtml(row.google_maps_address || "未提供")}</strong></div>
            <div class="detail-row"><span>Place ID</span><strong>${escapeHtml(row.google_maps_place_id || "未提供")}</strong></div>
            ${mapsLink ? `<div style="margin-top:10px;">${mapsLink}</div>` : ""}
          </div>
        `;
      }

      const optionsHtml = TRACKING_STATUSES.map((option) => (
        `<option value="${htmlAttr(option)}"${trackingStatus === option ? " selected" : ""}>${escapeHtml(option)}</option>`
      )).join("");

      return `
        <article class="lead-card"
          data-lead-id="${htmlAttr(row.lead_id)}"
          data-source="${htmlAttr(row.source_tag || "")}"
          data-tracking-status="${htmlAttr(trackingStatus)}"
          data-owner="${htmlAttr((row.tracking_owner || "").toLowerCase())}"
          data-search="${htmlAttr(cardSearchBlob(row))}">
          <div class="card-top">
            <span class="source-pill">${escapeHtml(row.source_tag || "未知來源")}</span>
            <span class="budget-pill">${escapeHtml(formatMoney(row.construction_cost))}</span>
          </div>
          <h3>${escapeHtml(row.project_name || "未命名建案")}</h3>
          <div class="lead-meta">Lead ID：${escapeHtml(row.lead_id || "")}</div>
          <div class="details-grid">${detailsHtml}</div>
          ${registryHtml}
          ${mapsHtml}
          <div class="subsection tracking-box">
            <div class="subsection-head">
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <strong>追蹤欄位</strong>
                <span class="tracking-pill js-tracking-pill">${escapeHtml(trackingStatus)}</span>
              </div>
              <span class="${saveStateClass(saveStatus)} js-save-pill">${escapeHtml(saveStateText(saveStatus))}</span>
            </div>
            <div class="tracking-grid">
              <label class="field">
                <span>狀態</span>
                <select class="js-track-status">${optionsHtml}</select>
              </label>
              <label class="field">
                <span>負責人</span>
                <input class="js-track-owner" type="text" value="${htmlAttr(row.tracking_owner || "")}" placeholder="例如 Mandy">
              </label>
              <label class="field">
                <span>下次跟進</span>
                <input class="js-track-next-date" type="date" value="${htmlAttr(row.tracking_next_action_date || "")}">
              </label>
            </div>
            <label class="field">
              <span>備註</span>
              <textarea class="js-track-note" rows="3" placeholder="記錄聯絡窗口、需求、下一步">${escapeHtml(row.tracking_note || "")}</textarea>
            </label>
            <div class="muted" style="margin-top:10px;">
              最後更新：${escapeHtml(row.tracking_updated_at || row.last_crawled_at || "未提供")}
              ${row.tracking_updated_by_email ? "｜" + escapeHtml(row.tracking_updated_by_email) : ""}
            </div>
          </div>
        </article>
      `;
    }

    function updateSourceFilterOptions(rows) {
      const values = Array.from(new Set(rows.map((row) => row.source_tag).filter(Boolean)));
      const current = elements.sourceFilter.value;
      elements.sourceFilter.innerHTML = '<option value="">全部來源</option>' + values.map((value) => (
        `<option value="${htmlAttr(value)}">${escapeHtml(value)}</option>`
      )).join("");
      elements.sourceFilter.value = current;
    }

    function applyFilters() {
      const keyword = (elements.searchInput.value || "").trim().toLowerCase();
      const source = elements.sourceFilter.value;
      const trackingStatus = elements.trackingFilter.value;
      const ownerKeyword = (elements.ownerFilter.value || "").trim().toLowerCase();

      state.filteredRows = state.rows.filter((row) => {
        const haystack = cardSearchBlob(row);
        const matchesKeyword = !keyword || haystack.includes(keyword);
        const matchesSource = !source || (row.source_tag || "") === source;
        const matchesTracking = !trackingStatus || (row.tracking_status || "未處理") === trackingStatus;
        const matchesOwner = !ownerKeyword || String(row.tracking_owner || "").toLowerCase().includes(ownerKeyword);
        return matchesKeyword && matchesSource && matchesTracking && matchesOwner;
      });

      elements.summaryVisible.textContent = formatCount(state.filteredRows.length);
      elements.resultMeta.textContent = `目前顯示 ${formatCount(state.filteredRows.length)} / ${formatCount(state.rows.length)} 筆`;

      if (!state.filteredRows.length) {
        elements.leadGrid.innerHTML = '<div class="empty-state">這組篩選條件下沒有符合的案場。</div>';
        return;
      }

      elements.leadGrid.innerHTML = state.filteredRows.map(renderLeadCard).join("");
      bindCardEvents();
    }

    function updateRowFromCard(card) {
      const leadId = card.dataset.leadId;
      const row = state.rows.find((item) => item.lead_id === leadId);
      if (!row) {
        return null;
      }
      row.tracking_status = card.querySelector(".js-track-status").value || "未處理";
      row.tracking_owner = card.querySelector(".js-track-owner").value.trim();
      row.tracking_next_action_date = card.querySelector(".js-track-next-date").value || null;
      row.tracking_note = card.querySelector(".js-track-note").value.trim();
      row.tracking_updated_at = new Date().toISOString();
      row.tracking_updated_by_email = state.session?.user?.email || row.tracking_updated_by_email || "";
      return row;
    }

    function reflectCardState(card, row) {
      card.dataset.trackingStatus = row.tracking_status || "未處理";
      card.dataset.owner = String(row.tracking_owner || "").toLowerCase();
      const pill = card.querySelector(".js-tracking-pill");
      if (pill) {
        pill.textContent = row.tracking_status || "未處理";
      }
    }

    function setCardSaveState(card, status) {
      state.saveStates.set(card.dataset.leadId, status);
      const pill = card.querySelector(".js-save-pill");
      if (pill) {
        pill.className = saveStateClass(status);
        pill.textContent = saveStateText(status);
      }
    }

    async function persistCard(card) {
      const leadId = card.dataset.leadId;
      const row = updateRowFromCard(card);
      if (!row || !state.supabase || !state.session) {
        return;
      }
      reflectCardState(card, row);
      setCardSaveState(card, "saving");
      const payload = {
        tracking_status: row.tracking_status,
        tracking_owner: row.tracking_owner || null,
        tracking_next_action_date: row.tracking_next_action_date,
        tracking_note: row.tracking_note || null,
        tracking_updated_at: row.tracking_updated_at,
        tracking_updated_by_email: row.tracking_updated_by_email || null,
      };
      const { data, error } = await state.supabase
        .from(APP_CONFIG.sharedTable)
        .update(payload)
        .eq("lead_id", leadId)
        .select("*")
        .single();

      if (error) {
        setCardSaveState(card, "error");
        setAuthMessage("儲存追蹤欄位失敗：" + error.message, "danger");
        return;
      }

      const index = state.rows.findIndex((item) => item.lead_id === leadId);
      if (index >= 0 && data) {
        state.rows[index] = data;
      }
      setCardSaveState(card, "saved");
      applyFilters();
    }

    function queuePersist(card) {
      const leadId = card.dataset.leadId;
      reflectCardState(card, updateRowFromCard(card) || {});
      setCardSaveState(card, "saving");
      const previous = state.saveTimers.get(leadId);
      if (previous) {
        window.clearTimeout(previous);
      }
      const timer = window.setTimeout(() => {
        persistCard(card);
      }, 500);
      state.saveTimers.set(leadId, timer);
    }

    function bindCardEvents() {
      document.querySelectorAll(".lead-card").forEach((card) => {
        card.querySelectorAll(".js-track-status, .js-track-owner, .js-track-next-date, .js-track-note").forEach((field) => {
          field.addEventListener("change", () => queuePersist(card));
          field.addEventListener("input", () => queuePersist(card));
        });
      });
    }

    async function loadRows() {
      if (!state.supabase || !state.session) {
        return;
      }
      const email = state.session.user?.email || "";
      if (!isAllowedEmail(email)) {
        setAuthMessage("這個帳號不是允許的公司網域，無法查看內部資料。", "danger");
        elements.leadToolbar.classList.add("hidden");
        elements.leadGrid.innerHTML = '<div class="empty-state">只有 @' + escapeHtml(APP_CONFIG.allowedEmailDomain) + ' 帳號可以查看。</div>';
        return;
      }

      elements.refreshButton.disabled = true;
      setAuthMessage("正在載入內部名單...", "warn");

      const { data, error } = await state.supabase
        .from(APP_CONFIG.sharedTable)
        .select("*")
        .order("construction_cost", { ascending: false })
        .limit(APP_CONFIG.maxProjects || 500);

      elements.refreshButton.disabled = false;

      if (error) {
        state.rows = [];
        state.filteredRows = [];
        elements.leadToolbar.classList.add("hidden");
        elements.leadGrid.innerHTML = '<div class="empty-state">讀取共享名單失敗。請確認 Supabase table 與 RLS 已設定完成。</div>';
        setAuthMessage("資料庫讀取失敗：" + error.message, "danger");
        updateSummary();
        return;
      }

      state.rows = data || [];
      updateSourceFilterOptions(state.rows);
      elements.leadToolbar.classList.remove("hidden");
      setAuthMessage("已登入：" + email + "，可查看並保存追蹤欄位。", "ok");
      applyFilters();
    }

    async function sendMagicLink() {
      const email = (elements.emailInput.value || "").trim();
      if (!email) {
        setAuthMessage("請先輸入公司信箱。", "warn");
        return;
      }
      if (!isAllowedEmail(email)) {
        setAuthMessage("目前只接受 @" + APP_CONFIG.allowedEmailDomain + " 信箱登入。", "danger");
        return;
      }
      if (!state.supabase) {
        setAuthMessage("Supabase 公開金鑰尚未設定，還不能登入。", "danger");
        return;
      }

      elements.sendMagicLinkButton.disabled = true;
      setAuthMessage("正在寄送登入連結...", "warn");
      const redirectTo = window.location.href.split("#")[0];
      const { error } = await state.supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: redirectTo,
          shouldCreateUser: true,
        },
      });
      elements.sendMagicLinkButton.disabled = false;

      if (error) {
        setAuthMessage("寄送登入連結失敗：" + error.message, "danger");
        return;
      }
      setAuthMessage("登入連結已寄出，請到信箱點開 magic link。", "ok");
    }

    async function signOut() {
      if (!state.supabase) {
        return;
      }
      await state.supabase.auth.signOut();
    }

    async function handleSession(session) {
      state.session = session;
      if (session?.user?.email) {
        elements.signOutButton.classList.remove("hidden");
        await loadRows();
      } else {
        elements.signOutButton.classList.add("hidden");
        elements.leadToolbar.classList.add("hidden");
        state.rows = [];
        state.filteredRows = [];
        elements.leadGrid.innerHTML = '<div class="empty-state">登入後即可查看內部案場名單。</div>';
        setAuthMessage("尚未登入。", "");
        updateSummary();
      }
    }

    function bindTopLevelEvents() {
      elements.sendMagicLinkButton.addEventListener("click", sendMagicLink);
      elements.signOutButton.addEventListener("click", signOut);
      [elements.searchInput, elements.sourceFilter, elements.trackingFilter, elements.ownerFilter].forEach((field) => {
        field.addEventListener("input", applyFilters);
        field.addEventListener("change", applyFilters);
      });
      elements.refreshButton.addEventListener("click", loadRows);
    }

    async function init() {
      elements.allowedDomainLabel.textContent = "@" + APP_CONFIG.allowedEmailDomain;
      renderSourceCards();
      renderFilterChips();
      updateSummary();
      bindTopLevelEvents();

      if (!APP_CONFIG.supabaseUrl || !APP_CONFIG.supabaseKey) {
        setAuthMessage("尚未設定 Supabase 公開金鑰。先把 README 裡的 Secrets / SQL 設好後再重跑 workflow。", "danger");
        return;
      }

      state.supabase = createClient(APP_CONFIG.supabaseUrl, APP_CONFIG.supabaseKey);
      const { data } = await state.supabase.auth.getSession();
      await handleSession(data.session);
      state.supabase.auth.onAuthStateChange(async (_event, session) => {
        await handleSession(session);
      });
    }

    init();
  </script>
</body>
</html>
"""
    return html.replace("__CONFIG_JSON__", config_json).replace(
        "__SUMMARY_JSON__", summary_json
    )


def write_secure_site(site_output_dir: str, payload: dict[str, Any], app_config: dict[str, Any]) -> None:
    output_dir = Path(site_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    html = build_secure_site_html(payload, app_config)
    output_files = ["index.html"]
    alias_name = str(app_config.get("report_alias_name") or "").strip()
    if alias_name:
        output_files.append(alias_name)
    for name in output_files:
        path = output_dir / name
        path.write_text(html, encoding="utf-8")
        print(f"Wrote secure shared site to: {path}")
