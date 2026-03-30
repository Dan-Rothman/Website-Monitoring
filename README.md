# Website Monitor

A lightweight Python script that polls a website on a fixed interval and sends email alerts when it goes down or recovers.

## What it does

- Checks the configured URL every N minutes (default: 15)
- Sends an email alert when the site returns an HTTP error or becomes unreachable
- Sends a recovery email when the site comes back up
- Logs all activity to `monitor.log` and stdout

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
| `site_url` | The URL to monitor |
| `check_interval_minutes` | How often to check (in minutes) |
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
