# Website Monitor

A lightweight Python script that polls a website on a fixed interval and sends email alerts when it goes down or recovers.

## What it does

- Checks the configured URL every N minutes (default: 15)
- Sends an email alert when the site returns an HTTP error or becomes unreachable
- Sends a recovery email when the site comes back up
- Logs all activity to `monitor.log` and stdout
- Records every check as a row in a local SQLite database (`monitor.db`) with the following columns:

| Column | Description |
|---|---|
| `timestamp` | Date and time the check ran |
| `url` | URL that was checked |
| `status_code` | HTTP status code returned |
| `reason` | HTTP reason phrase, `Timeout`, or `Internet Out` |
| `elapsed_seconds` | Round-trip response time in seconds |
| `final_url` | URL after any redirects |
| `redirect_count` | Number of redirects followed |
| `server` | Web server software from response headers |
| `content_type` | Content-Type from response headers |
| `content_length` | Content-Length from response headers |

Timeout and internet outage rows record `null` for all columns except `timestamp`, `url`, `elapsed_seconds`, and `reason`.

## Querying the database

**DB Browser for SQLite** *(recommended)* — a free GUI app that lets you browse and filter the `responses` table without writing any code, and export to CSV. Download at [sqlitebrowser.org](https://sqlitebrowser.org/).

**Excel** — Data → Get Data → From Database → From SQLite. Loads the table directly into a spreadsheet for filtering and charting.

**Command line** — requires `sqlite3.exe` ([sqlite.org/download.html](https://sqlite.org/download.html)), drop it in the project folder and run:

```bash
sqlite3 monitor.db
SELECT * FROM responses ORDER BY timestamp DESC LIMIT 20;
SELECT * FROM responses WHERE reason IS NOT NULL;
SELECT * FROM responses WHERE timestamp >= '2026-04-01';
.quit
```

## Requirements

- Python 3.8+

## Setup

**1. Clone the repo and enter the directory**

```bash
git clone https://github.com/your-username/website-monitor.git
cd website-monitor
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

Or on Windows, just double-click `run.bat` — it handles everything automatically.

**3. Configure**

Copy the example config and fill in your values:

```bash
cp config.example.json config.json
```

Edit `config.json`:

| Field | Description |
|---|---|
| `sites` | List of sites to monitor (one or more) |
| `sites.name` | Name of site used in alert emails |
| `sites.url` | The URL of the site |
| `check_interval_minutes` | How often to check (in minutes) |
| `timeout_seconds` | Seconds to wait for a response before considering the request timed out (default: 15) |
| `smtp.host` | SMTP server (e.g. `smtp.gmail.com`) |
| `smtp.port` | SMTP port (587 for TLS) |
| `smtp.sender_email` | Email address used to send alerts |
| `smtp.app_password` | App password for the sender account |
| `alert_recipients` | List of email addresses to notify |

> **Gmail users:** Use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password. App Passwords require 2-Step Verification to be enabled on your account.

## Running

```bash
python monitor.py
```

Or on Windows:

```
run.bat
```

The script runs continuously until stopped with `Ctrl+C`.
