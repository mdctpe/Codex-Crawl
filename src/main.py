from __future__ import annotations

import os
from datetime import datetime, timezone


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


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Crawler started at: {started_at}")

    load_environment()

    required_secrets = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    missing = [name for name in required_secrets if not configured(name)]

    if missing:
        print("Supabase configuration is incomplete.")
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Skipping crawler work and exiting successfully.")
        return 0

    print("Supabase configuration found.")
    print("SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
    print("Crawler configuration check completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
