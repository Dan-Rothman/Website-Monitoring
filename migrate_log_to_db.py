"""
Migration script: import monitor.log entries into monitor.db

Reads the text log produced by older versions of the monitor and inserts one
row per UP/DOWN event into the SQLite database used by the current version.

Fields not available in the text log (server, content_type, etc.) are left NULL.

Usage:
    python migrate_log_to_db.py [log_file] [db_file]

Defaults to monitor.log and monitor.db in the same directory as this script.
"""

import re
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
DEFAULT_LOG = BASE_DIR / "monitor.log"
DEFAULT_DB  = BASE_DIR / "monitor.db"

# Matches: 2026-03-30 17:16:49,151 [INFO] UP — https://example.com (200)
UP_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+\[INFO\]\s+UP\s+\S+\s+(https?://\S+)\s+\((\d+)\)"
)

# Matches: 2026-03-30 17:16:49,151 [WARNING] DOWN — https://example.com (some reason)
# Captures everything inside the outermost trailing parentheses as the reason.
DOWN_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+\[WARNING\]\s+DOWN\s+\S+\s+(https?://\S+)\s+\((.+)\)$"
)

# Extracts elapsed seconds from "Request timed out (>15s)"
TIMEOUT_SECONDS_PATTERN = re.compile(r">(\d+(?:\.\d+)?)s")


def init_db(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT    NOT NULL,
                url             TEXT,
                status_code     INTEGER,
                reason          TEXT,
                elapsed_seconds REAL,
                final_url       TEXT,
                redirect_count  INTEGER,
                server          TEXT,
                content_type    TEXT,
                content_length  INTEGER
            )
        """)


def parse_down_reason(raw_reason):
    """Return (reason, elapsed_seconds) from the text inside the trailing parens."""
    raw = raw_reason.strip()

    # "Request timed out (>15s)" — may itself contain parens
    if raw.startswith("Request timed out"):
        m = TIMEOUT_SECONDS_PATTERN.search(raw)
        elapsed = float(m.group(1)) if m else None
        return "Timeout", elapsed

    # "HTTP 404" — extract numeric status for the reason field
    if re.match(r"HTTP \d+", raw):
        return raw, None

    # "Connection refused or DNS failure" and any other plain reason
    return raw, None


def migrate(log_path, db_path):
    init_db(db_path)
    rows = []

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()

            m = UP_PATTERN.match(line)
            if m:
                timestamp, url, status_code = m.group(1), m.group(2), int(m.group(3))
                rows.append({
                    "timestamp": timestamp,
                    "url": url,
                    "status_code": status_code,
                    "reason": None,
                    "elapsed_seconds": None,
                })
                continue

            m = DOWN_PATTERN.match(line)
            if m:
                timestamp, url, raw_reason = m.group(1), m.group(2), m.group(3)
                reason, elapsed = parse_down_reason(raw_reason)
                status_code = None
                if reason.startswith("HTTP "):
                    try:
                        status_code = int(reason.split()[1])
                    except (IndexError, ValueError):
                        pass
                rows.append({
                    "timestamp": timestamp,
                    "url": url,
                    "status_code": status_code,
                    "reason": reason,
                    "elapsed_seconds": elapsed,
                })

    if not rows:
        print("No UP/DOWN entries found in the log file.")
        return

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO responses (
                timestamp, url, status_code, reason, elapsed_seconds,
                final_url, redirect_count, server, content_type, content_length
            ) VALUES (
                :timestamp, :url, :status_code, :reason, :elapsed_seconds,
                NULL, NULL, NULL, NULL, NULL
            )
            """,
            rows,
        )

    print(f"Inserted {len(rows)} rows from '{log_path}' into '{db_path}'.")


if __name__ == "__main__":
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG
    db_path  = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB

    if not log_path.exists():
        print(f"Error: log file not found: {log_path}")
        sys.exit(1)

    migrate(log_path, db_path)
