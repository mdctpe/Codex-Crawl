# Minimal Python Crawler

This repository is a small Python crawler designed to run in GitHub Actions every Monday and on demand.

## Requirements

- Python 3.11 for CI
- Dependencies from `requirements.txt`

## Environment Variables

The crawler checks these variables when it starts:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GOOGLE_MAPS_API_KEY`
- `NLMA_BMLIC_API_URL`
- `GCIS_COMPANY_LOOKUP_ENABLED`
- `GCIS_COMPANY_KEYWORD_API_URL`
- `GCIS_COMPANY_DETAILS_API_URL`
- `NEW_TAIPEI_JSON_URL`
- `NEW_TAIPEI_PAGE_SIZE`
- `NEW_TAIPEI_MAX_PAGES`
- `TAIPEI_HISTORY_XML_URL`
- `TAIPEI_CURRENT_XML_URL`
- `PERMIT_START_DATE`
- `PERMIT_END_DATE`
- `MIN_CONSTRUCTION_COST`
- `MAX_PROJECTS`
- `TARGET_USAGES`
- `REPORT_PATH`
- `INDEX_PATH`
- `TRACKER_PATH`

If the Supabase secrets are missing, the script prints a clear message and continues. If they are present, matching permits can also be upserted into the `leads` table.

If `GOOGLE_MAPS_API_KEY` is missing, the script skips the Google Maps enrichment step and still exits successfully.

By default the crawler calls the official NLMA open data building permit endpoint:

`https://cloudbm.nlma.gov.tw/eweb/OpenData/OAS/EIX_RSAPI_V1/opendata/bmlic`

It also fetches New Taipei City's official building permit open data:

`https://data.ntpc.gov.tw/api/datasets/C1487D7B-FFF1-43D3-A2CE-4716EAB4D286/json`

It also fetches Taipei City's official building permit summary XML resources:

- `https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=2d9396af-863b-496a-9893-0d2f2a8d8b71`
- `https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=43624c8e-c768-4b3c-93c4-595f5af7a9cb`

For company normalization, the crawler can also enrich matched developers through the official GCIS company registry APIs:

- `https://data.gcis.nat.gov.tw/od/data/api/6BBA2268-1367-4B42-9CCA-BC17499EBE8C`
- `https://data.gcis.nat.gov.tw/od/data/api/236EE382-4942-41A9-BD03-CA0709025E7C`

The current implementation:

- fetches permit records from NLMA, New Taipei City, Taipei City, and Taichung City
- filters by date range, minimum construction cost, and target usage keywords
- optionally normalizes company names with GCIS and adds company registry details
- prints the matching permits
- optionally enriches each permit with Google Maps text search
- writes a structured `results/results.json` output file
- generates a human-friendly HTML report for the team
- creates a share-ready `results/index.html` page and a `results/tracker.csv` file for Google Sheets or Excel follow-up

## Local Configuration

Create a local `.env` file from `.env.example` and fill in your own values.

Do not paste API keys into chat messages. Put them in `.env` locally or in GitHub Secrets.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.main
```

Example local run with Google Maps enabled:

```bash
GOOGLE_MAPS_API_KEY=your-key python -m src.main
```

After the run finishes, inspect:

`results/results.json`

and

`results/report.html`

The shareable static page will also be written to:

`results/index.html`

The starter tracker file for teammates is:

`results/tracker.csv`

## GitHub Configuration

Add these in `Settings -> Secrets and variables -> Actions`:

Secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GOOGLE_MAPS_API_KEY`

Variables:

- `NLMA_BMLIC_API_URL`
- `GCIS_COMPANY_LOOKUP_ENABLED`
- `GCIS_COMPANY_KEYWORD_API_URL`
- `GCIS_COMPANY_DETAILS_API_URL`
- `NEW_TAIPEI_JSON_URL`
- `NEW_TAIPEI_PAGE_SIZE`
- `NEW_TAIPEI_MAX_PAGES`
- `TAIPEI_HISTORY_XML_URL`
- `TAIPEI_CURRENT_XML_URL`
- `PERMIT_START_DATE`
- `PERMIT_END_DATE`
- `MIN_CONSTRUCTION_COST`
- `MAX_PROJECTS`
- `TARGET_USAGES`

## GitHub Actions

The workflow lives at `.github/workflows/weekly-crawl.yml` and runs:

- every Monday at `00:00` UTC
- whenever `workflow_dispatch` is triggered manually

Each workflow run uploads `results/results.json` as an artifact named `weekly-crawl-results`.
The artifact now includes the HTML report, shareable index page, and tracker CSV.

The workflow also deploys the latest `results/` folder to GitHub Pages so teammates can open a stable URL after the branch is merged or the workflow is run from the publishing branch.
