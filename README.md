# Minimal Python Crawler

This repository is a small Python crawler scaffold designed to run in GitHub Actions every Monday and on demand.

## Requirements

- Python 3.11 for CI
- Dependencies from `requirements.txt`

## Environment Variables

The crawler checks these variables when it starts:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

If either secret is missing, the script prints a clear message and exits successfully so scheduled runs do not fail while configuration is still in progress.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.main
```

## GitHub Actions

The workflow lives at `.github/workflows/weekly-crawl.yml` and runs:

- every Monday at `00:00` UTC
- whenever `workflow_dispatch` is triggered manually
