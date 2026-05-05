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
- `NEW_TAIPEI_JSON_URL`
- `NEW_TAIPEI_PAGE_SIZE`
- `NEW_TAIPEI_MAX_PAGES`
- `PERMIT_START_DATE`
- `PERMIT_END_DATE`
- `MIN_CONSTRUCTION_COST`
- `MAX_PROJECTS`
- `TARGET_USAGES`

If the Supabase secrets are missing, the script prints a clear message and continues because the scaffold does not write to Supabase yet.

If `GOOGLE_MAPS_API_KEY` is missing, the script skips the Google Maps enrichment step and still exits successfully.

By default the crawler calls the official NLMA open data building permit endpoint:

`https://cloudbm.nlma.gov.tw/eweb/OpenData/OAS/EIX_RSAPI_V1/opendata/bmlic`

It also fetches New Taipei City's official building permit open data:

`https://data.ntpc.gov.tw/api/datasets/C1487D7B-FFF1-43D3-A2CE-4716EAB4D286/json`

The current implementation:

- fetches permit records from NLMA, New Taipei City, and Taichung City
- filters by date range, minimum construction cost, and target usage keywords
- prints the matching permits
- optionally enriches each permit with Google Maps text search
- writes a structured `results/results.json` output file

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

## GitHub Configuration

Add these in `Settings -> Secrets and variables -> Actions`:

Secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GOOGLE_MAPS_API_KEY`

Variables:

- `NLMA_BMLIC_API_URL`
- `NEW_TAIPEI_JSON_URL`
- `NEW_TAIPEI_PAGE_SIZE`
- `NEW_TAIPEI_MAX_PAGES`
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
