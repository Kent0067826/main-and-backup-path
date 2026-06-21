# Service Maintenance Tracker

Track network service maintenance windows and automatically detect service disruptions caused by overlapping maintenance activities.

## Problem

Each network service has a **main path** and a **backup path**. When two different maintenance tickets (PW/EW/FI) overlap in time and together affect **both paths** of the same service, that service will be **disrupted**. This tool automates that analysis.

## Features

- **Ticket Management** — Add, modify, and delete maintenance tickets (PW/EW/FI). End time is optional for ongoing maintenance.
- **Auto-extract Service IDs** — Paste raw text and all `WL`-prefixed IDs are extracted automatically.
- **Disruption Detection** — Cross-ticket only: same-ticket overlap does not count (we should handle it when creating the PW/EW/FI). Automatically computes exact overlap windows and recalculates on every change.
- **Overlapping Ticket Pairs** — Groups disrupted services by ticket pair (both directions), with per-pair service count.
- **Reschedule Impossible** — Mark tickets the provider cannot reschedule. Visual indicators propagate into the ticket pair view.
- **Update Notes** — Zabbix-style timestamped notes on each disruption and ticket pair for tracking DI tickets, communication, and decisions.
- **Collapsible UI** — All items collapse to a single row; click to expand.

## Quick Start

```bash
git clone https://github.com/Kent0067826/main-and-backup-path.git
cd main-and-backup-path
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5001`. Time format: `DD.MM.YYYY HH:MM UTC`.

## Tech Stack

Python / Flask, SQLite, Gunicorn + systemd. Data stored in `maintenance.db`.
