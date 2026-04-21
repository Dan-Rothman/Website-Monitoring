import json
import logging
import smtplib
import sqlite3
import sys
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

import requests
import schedule

# --- Config ---

CONFIG_FILE = Path(__file__).parent / "config.json"
DB_FILE = Path(__file__).parent / "monitor.db"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# --- Logging ---

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent / "monitor.log"),
    ],
)
log = logging.getLogger(__name__)

# --- Database ---

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
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

def log_response_row(
    timestamp, url=None, status_code=None, reason=None,
    elapsed_seconds=None, final_url=None, redirect_count=None,
    server=None, content_type=None, content_length=None,
):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO responses (
                timestamp, url, status_code, reason, elapsed_seconds,
                final_url, redirect_count, server, content_type, content_length
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp, url, status_code, reason, elapsed_seconds,
                final_url, redirect_count, server, content_type, content_length,
            ),
        )

# --- State ---

site_was_down = {}  # keyed by URL

# --- Email ---

def send_email(config, subject, body):
    smtp = config["smtp"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp["sender_email"]
    msg["To"] = ", ".join(config["alert_recipients"])
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(smtp["host"], smtp["port"]) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp["sender_email"], smtp["app_password"])
        server.sendmail(smtp["sender_email"], config["alert_recipients"], msg.as_string())

def send_down_alert(config, site, reason):
    url = site["url"]
    name = site["name"]
    subject = f"[DOWN] {name}-{reason}"
    body = (
        f"Website monitoring alert\n"
        f"Status : DOWN\n"
        f"URL    : {url}\n"
        f"Reason : {reason}\n"
        f"Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    send_email(config, subject, body)
    log.info("Down alert sent for %s", url)

def send_recovery_alert(config, site):
    url = site["url"]
    name = site["name"]
    subject = f"[RECOVERED] {name}"
    body = (
        f"Website monitoring alert\n"
        f"Status : RECOVERED\n"
        f"URL    : {url}\n"
        f"Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    send_email(config, subject, body)
    log.info("Recovery alert sent for %s", url)

# --- Network ---

def has_internet_connectivity(timeout_seconds):
    try:
        requests.get("https://www.google.com", timeout=timeout_seconds)
        return True
    except Exception:
        return False

# --- Check ---

def check_site(site):
    url = site["url"]
    global site_was_down
    config = load_config()
    timeout_seconds = config.get("timeout_seconds", 15)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        response = requests.get(url, timeout=timeout_seconds)

        log_response_row(
            timestamp=timestamp,
            url=url,
            status_code=response.status_code,
            reason=response.reason,
            elapsed_seconds=response.elapsed.total_seconds(),
            final_url=response.url,
            redirect_count=len(response.history),
            server=response.headers.get("Server"),
            content_type=response.headers.get("Content-Type"),
            content_length=response.headers.get("Content-Length"),
        )

        if response.status_code < 400:
            log.info("UP — %s (%d)", url, response.status_code)
            if site_was_down.get(url):
                site_was_down[url] = False
                try:
                    send_recovery_alert(config, site)
                except Exception as e:
                    log.error("Failed to send recovery alert: %s", e)
        else:
            reason = f"HTTP {response.status_code}"
            log.warning("DOWN — %s (%s)", url, reason)
            if not site_was_down.get(url):
                site_was_down[url] = True
                try:
                    send_down_alert(config, site, reason)
                except Exception as e:
                    log.error("Failed to send down alert: %s", e)

    except requests.exceptions.ConnectionError:
        reason = "Connection refused or DNS failure"
        log.warning("DOWN — %s (%s)", url, reason)
        if not has_internet_connectivity(timeout_seconds):
            log.warning("Google.com also unreachable — likely a local network issue; skipping alert")
            log_response_row(timestamp=timestamp, url=url, reason="Internet Out")
            return
        log_response_row(timestamp=timestamp, url=url, reason=reason)
        if not site_was_down.get(url):
            site_was_down[url] = True
            try:
                send_down_alert(config, site, reason)
            except Exception as e:
                log.error("Failed to send down alert: %s", e)

    except requests.exceptions.Timeout:
        log.warning("DOWN — %s (timed out after %ss)", url, timeout_seconds)
        if not has_internet_connectivity(timeout_seconds):
            log.warning("Google.com also unreachable — likely a local network issue; skipping alert")
            log_response_row(timestamp=timestamp, url=url, elapsed_seconds=timeout_seconds, reason="Internet Out")
            return
        log_response_row(timestamp=timestamp, url=url, elapsed_seconds=timeout_seconds, reason="Timeout")
        if not site_was_down.get(url):
            site_was_down[url] = True
            try:
                send_down_alert(config, site, f"Request timed out (>{timeout_seconds}s)")
            except Exception as e:
                log.error("Failed to send down alert: %s", e)

    except Exception as e:
        log.error("Unexpected error checking %s: %s", url, e)

# --- Main ---

if __name__ == "__main__":
    init_db()
    config = load_config()
    interval = config.get("check_interval_minutes", 15)
    sites = config["sites"]

    log.info("Starting monitor for %d site(s) — checking every %d minutes", len(sites), interval)
    for site in sites:
        log.info("  • %s", site)

    for site in sites:
        check_site(site)
        schedule.every(interval).minutes.do(check_site, site)

    while True:
        schedule.run_pending()
        time.sleep(30)
