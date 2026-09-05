#!/bin/sh
set -e

# Wait for PostgreSQL to be ready before starting.
# Railway injects DATABASE_URL from the linked Postgres service.
echo "Waiting for PostgreSQL..."
until python - <<'EOF'
import os, sys
try:
    import sqlalchemy
    engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
    with engine.connect():
        pass
    print("PostgreSQL is ready.")
except Exception as e:
    print(f"Not ready: {e}", file=sys.stderr)
    sys.exit(1)
EOF
do
  sleep 3
done

# Create tables if they don't exist.
python - <<'EOF'
from backend.db import create_tables
from backend.db.migrations.runner import run_migrations
create_tables()
run_migrations()
print("Tables and migrations ready.")
EOF

# Run the pipeline on a schedule.
# PIPELINE_INTERVAL_HOURS controls how often it runs (default: 24).
python - <<'EOF'
import os, time, subprocess, sys

interval = int(os.environ.get("PIPELINE_INTERVAL_HOURS", "24")) * 3600
days = int(os.environ.get("SCRAPER_DAYS", "7"))

while True:
    print("Starting pipeline run...", flush=True)
    scraper = "/app/backend/scraper/src/mas_regulations_scraper.py"
    if os.path.exists(scraper):
        result = subprocess.run(
            ["python", scraper, "--days", str(days), "--download-pdfs"],
            cwd="/app",
        )
        if result.returncode != 0:
            print("Scraper failed, skipping pipeline step.", file=sys.stderr, flush=True)
            time.sleep(interval)
            continue

    subprocess.run(["python", "-m", "backend.pipeline"], cwd="/app")

    print(f"Run complete. Next run in {interval // 3600}h.", flush=True)
    time.sleep(interval)
EOF
