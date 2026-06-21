# Service Maintenance Tracker

A web application for tracking network service maintenance windows and automatically detecting service disruptions caused by overlapping maintenance activities.

## Problem

Each network service has a **main path** and a **backup path**. When a maintenance window affects only one path, the service stays online via the other. But when two different maintenance tickets overlap in time and together affect **both paths** of the same service, that service will be **disrupted**.

Manually tracking these overlaps across dozens of tickets and hundreds of services is error-prone. This tool automates that analysis.

## Features

### Maintenance Ticket Management
- Add maintenance tickets with ticket number, time window, and affected services
- **Auto-extract Service IDs** from pasted text — just paste raw data and all `WL`-prefixed IDs are extracted automatically
- Modify ticket time windows and affected services at any time
- Delete tickets when no longer needed

### Disruption Detection
- **Cross-ticket only** — if the same ticket affects both paths of a service, it does not count as a disruption (we should handle it when creating the PW/EW/FI)
- Automatically computes the exact overlap time window when different tickets cause a disruption
- Recalculates all disruptions whenever tickets are added, modified, or deleted

### Overlapping Ticket Pairs
- Groups all affected services by ticket pair
- Combines both directions: Ticket A → main + Ticket B → backup, and Ticket A → backup + Ticket B → main
- Shows the count of disrupted services per pair for quick assessment

### Reschedule Impossible
- Mark a maintenance ticket as "Reschedule Impossible" when the provider cannot change the maintenance window
- Visual indicators propagate into the Overlapping Ticket Pairs view so you can immediately see which overlaps have no flexibility

### Update Notes(to add DI ticket or any updates on each overflap)
- Zabbix-style timestamped notes on each disruption and ticket pair
- Track communication history, decisions, and status updates

### Collapsible UI
- All disruption items and ticket pairs collapse to a single summary row
- Click to expand and see full details — keeps the page manageable with many entries

## Tech Stack

- **Backend**: Python / Flask
- **Database**: SQLite (file-based, no external DB server needed)
- **Production server**: Gunicorn + systemd

## Quick Start

```bash
git clone https://github.com/Kent0067826/main-and-backup-path.git
cd main-and-backup-path
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5001` in your browser.

## Deployment

The app runs as a systemd service with Gunicorn:

```bash
# Install dependencies
apt install python3-pip python3-venv git
cd /opt/maintenance-tracker
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Start with Gunicorn
venv/bin/gunicorn app:app --bind 0.0.0.0:5001 --workers 2
```

## Time Format

All times use the format `DD.MM.YYYY HH:MM UTC`, for example: `25.06.2026 21:00 UTC`

## Data Storage

All data is stored in `maintenance.db` (SQLite) in the application directory. Back up this file to preserve your data.
