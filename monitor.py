import json
import logging
import smtplib
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

# --- State ---

site_was_down = False

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

def send_down_alert(config, url, reason):
    subject = f"[DOWN] {url}"
    body = (
        f"Website monitoring alert\n"
        f"{'=' * 40}\n"
        f"Status : DOWN\n"
        f"URL    : {url}\n"
        f"Reason : {reason}\n"
        f"Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    send_email(config, subject, body)
    log.info("Down alert sent for %s", url)

def send_recovery_alert(config, url):
    subject = f"[RECOVERED] {url}"
    body = (
        f"Website monitoring alert\n"
        f"{'=' * 40}\n"
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

def check_site():
    global site_was_down
    config = load_config()
    url = config["site_url"]

    timeout_seconds = config.get("timeout_seconds", 15)

    try:
        response = requests.get(url, timeout=timeout_seconds)
        if response.status_code < 400:
            log.info("UP — %s (%d)", url, response.status_code)
            if site_was_down:
                site_was_down = False
                try:
                    send_recovery_alert(config, url)
                except Exception as e:
                    log.error("Failed to send recovery alert: %s", e)
        else:
            reason = f"HTTP {response.status_code}"
            log.warning("DOWN — %s (%s)", url, reason)
            if not site_was_down:
                site_was_down = True
                try:
                    send_down_alert(config, url, reason)
                except Exception as e:
                    log.error("Failed to send down alert: %s", e)

    except requests.exceptions.ConnectionError:
        reason = "Connection refused or DNS failure"
        log.warning("DOWN — %s (%s)", url, reason)
        if not site_was_down:
            site_was_down = True
            try:
                send_down_alert(config, url, reason)
            except Exception as e:
                log.error("Failed to send down alert: %s", e)

    except requests.exceptions.Timeout:
        reason = f"Request timed out (>{timeout_seconds}s)"
        log.warning("DOWN — %s (%s)", url, reason)
        if not has_internet_connectivity(timeout_seconds):
            log.warning("Google.com also unreachable — likely a local network issue; skipping alert")
            return
        if not site_was_down:
            site_was_down = True
            try:
                send_down_alert(config, url, reason)
            except Exception as e:
                log.error("Failed to send down alert: %s", e)

    except Exception as e:
        log.error("Unexpected error checking %s: %s", url, e)

# --- Main ---

if __name__ == "__main__":
    config = load_config()
    interval = config.get("check_interval_minutes", 15)
    url = config["site_url"]

    log.info("Starting monitor for %s — checking every %d minutes", url, interval)

    # Run once immediately on startup
    check_site()

    schedule.every(interval).minutes.do(check_site)

    while True:
        schedule.run_pending()
        time.sleep(30)
