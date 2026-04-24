# Minimal Python Crawler

This repository is a small Python crawler scaffold designed to run in GitHub Actions every Monday and on demand.

## Requirements

- Python 3.11 for CI
- Dependencies from `requirements.txt`

## Environment Variables

The crawler checks these variables when it starts:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GOOGLE_MAPS_API_KEY`

If the Supabase secrets are missing, the script prints a clear message and continues because the scaffold does not write to Supabase yet.

If `GOOGLE_MAPS_API_KEY` is missing, the script skips the Google Maps enrichment step and exits successfully so scheduled runs do not fail while configuration is still in progress.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.main
```

To test the Google Maps path locally:

```bash
GOOGLE_MAPS_API_KEY=your-key python -m src.main
```

## GitHub Actions

The workflow lives at `.github/workflows/weekly-crawl.yml` and runs:

- every Monday at `00:00` UTC
- whenever `workflow_dispatch` is triggered manually
