from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime
import os
import re

app = Flask(__name__)
app.secret_key = "maint-tracker-key"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maintenance.db")
TIME_FMT = "%d.%m.%Y %H:%M"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_number TEXT NOT NULL UNIQUE,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS affected_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            maintenance_id INTEGER NOT NULL,
            service_id TEXT NOT NULL,
            path_type TEXT NOT NULL CHECK(path_type IN ('main', 'backup')),
            FOREIGN KEY (maintenance_id) REFERENCES maintenance(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS disruption_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def parse_time(s):
    s = s.strip()
    if s.upper().endswith(" UTC"):
        s = s[:-4].strip()
    return datetime.strptime(s, TIME_FMT)


def fmt(dt):
    return dt.strftime(TIME_FMT) + " UTC"


def extract_service_ids(text):
    return re.findall(r"WL[A-Z]*-[\w.\-]+", text)


def union_intervals(intervals):
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: x[0])
    merged = [list(sorted_iv[0])]
    for start, end in sorted_iv[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def calculate_disruptions():
    """Per-service disruptions, only counting CROSS-TICKET overlaps."""
    conn = get_db()
    services = conn.execute("SELECT DISTINCT service_id FROM affected_paths").fetchall()
    disruptions = []

    for row in services:
        sid = row["service_id"]

        main_rows = conn.execute("""
            SELECT m.ticket_number, m.start_time, m.end_time
            FROM maintenance m
            JOIN affected_paths ap ON m.id = ap.maintenance_id
            WHERE ap.service_id = ? AND ap.path_type = 'main'
        """, (sid,)).fetchall()

        backup_rows = conn.execute("""
            SELECT m.ticket_number, m.start_time, m.end_time
            FROM maintenance m
            JOIN affected_paths ap ON m.id = ap.maintenance_id
            WHERE ap.service_id = ? AND ap.path_type = 'backup'
        """, (sid,)).fetchall()

        if not main_rows or not backup_rows:
            continue

        main_windows = [
            (datetime.fromisoformat(r["start_time"]), datetime.fromisoformat(r["end_time"]), r["ticket_number"])
            for r in main_rows
        ]
        backup_windows = [
            (datetime.fromisoformat(r["start_time"]), datetime.fromisoformat(r["end_time"]), r["ticket_number"])
            for r in backup_rows
        ]

        # Only count overlaps between DIFFERENT tickets
        cross_overlaps = []
        for ms, me, mt in main_windows:
            for bs, be, bt in backup_windows:
                if mt != bt:
                    os_ = max(ms, bs)
                    oe_ = min(me, be)
                    if os_ < oe_:
                        cross_overlaps.append((os_, oe_))

        if not cross_overlaps:
            continue

        merged = union_intervals(cross_overlaps)

        for d_start, d_end in merged:
            main_tickets = sorted(set(t for s, e, t in main_windows if s < d_end and e > d_start))
            backup_tickets = sorted(set(t for s, e, t in backup_windows if s < d_end and e > d_start))
            disruptions.append({
                "service_id": sid,
                "start": fmt(d_start),
                "end": fmt(d_end),
                "main_tickets": main_tickets,
                "backup_tickets": backup_tickets,
            })

    conn.close()
    disruptions.sort(key=lambda d: (d["service_id"], d["start"]))
    return disruptions


def calculate_ticket_pair_overlaps():
    """Group disrupted services by overlapping ticket pairs."""
    conn = get_db()
    all_tickets = conn.execute("SELECT * FROM maintenance ORDER BY start_time").fetchall()

    pairs = []
    for i in range(len(all_tickets)):
        for j in range(i + 1, len(all_tickets)):
            t1 = all_tickets[i]
            t2 = all_tickets[j]
            s1 = datetime.fromisoformat(t1["start_time"])
            e1 = datetime.fromisoformat(t1["end_time"])
            s2 = datetime.fromisoformat(t2["start_time"])
            e2 = datetime.fromisoformat(t2["end_time"])

            os_ = max(s1, s2)
            oe_ = min(e1, e2)
            if os_ >= oe_:
                continue

            t1_main = set(r["service_id"] for r in conn.execute(
                "SELECT service_id FROM affected_paths WHERE maintenance_id = ? AND path_type = 'main'",
                (t1["id"],)).fetchall())
            t1_backup = set(r["service_id"] for r in conn.execute(
                "SELECT service_id FROM affected_paths WHERE maintenance_id = ? AND path_type = 'backup'",
                (t1["id"],)).fetchall())
            t2_main = set(r["service_id"] for r in conn.execute(
                "SELECT service_id FROM affected_paths WHERE maintenance_id = ? AND path_type = 'main'",
                (t2["id"],)).fetchall())
            t2_backup = set(r["service_id"] for r in conn.execute(
                "SELECT service_id FROM affected_paths WHERE maintenance_id = ? AND path_type = 'backup'",
                (t2["id"],)).fetchall())

            # A->main + B->backup
            ab = t1_main & t2_backup
            # A->backup + B->main
            ba = t1_backup & t2_main

            all_services = ab | ba
            if not all_services:
                continue

            service_details = []
            for sid in sorted(all_services):
                main_by = []
                backup_by = []
                if sid in t1_main:
                    main_by.append(t1["ticket_number"])
                if sid in t2_main:
                    main_by.append(t2["ticket_number"])
                if sid in t1_backup:
                    backup_by.append(t1["ticket_number"])
                if sid in t2_backup:
                    backup_by.append(t2["ticket_number"])
                service_details.append({
                    "service_id": sid,
                    "main_tickets": main_by,
                    "backup_tickets": backup_by,
                })

            pair_key = f"PAIR:{t1['ticket_number']}+{t2['ticket_number']}"
            pairs.append({
                "ticket_a": t1["ticket_number"],
                "ticket_b": t2["ticket_number"],
                "pair_key": pair_key,
                "overlap_start": fmt(os_),
                "overlap_end": fmt(oe_),
                "services": service_details,
                "count": len(all_services),
            })

    conn.close()
    return pairs


@app.route("/")
def index():
    conn = get_db()
    tickets = conn.execute("SELECT * FROM maintenance ORDER BY start_time").fetchall()

    ticket_details = []
    for t in tickets:
        main_svcs = conn.execute(
            "SELECT service_id FROM affected_paths WHERE maintenance_id = ? AND path_type = 'main'",
            (t["id"],),
        ).fetchall()
        backup_svcs = conn.execute(
            "SELECT service_id FROM affected_paths WHERE maintenance_id = ? AND path_type = 'backup'",
            (t["id"],),
        ).fetchall()
        ticket_details.append({
            "id": t["id"],
            "ticket_number": t["ticket_number"],
            "start_time": fmt(datetime.fromisoformat(t["start_time"])),
            "end_time": fmt(datetime.fromisoformat(t["end_time"])),
            "main_services": [s["service_id"] for s in main_svcs],
            "backup_services": [s["service_id"] for s in backup_svcs],
        })

    disruptions = calculate_disruptions()
    ticket_pairs = calculate_ticket_pair_overlaps()

    notes_by_service = {}
    for d in disruptions:
        sid = d["service_id"]
        if sid not in notes_by_service:
            notes_rows = conn.execute(
                "SELECT message, created_at FROM disruption_notes WHERE service_id = ? ORDER BY created_at DESC",
                (sid,),
            ).fetchall()
            notes_by_service[sid] = [
                {"message": r["message"], "time": r["created_at"] + " UTC"} for r in notes_rows
            ]
        d["notes"] = notes_by_service[sid]

    for p in ticket_pairs:
        pk = p["pair_key"]
        notes_rows = conn.execute(
            "SELECT message, created_at FROM disruption_notes WHERE service_id = ? ORDER BY created_at DESC",
            (pk,),
        ).fetchall()
        p["notes"] = [{"message": r["message"], "time": r["created_at"] + " UTC"} for r in notes_rows]

    conn.close()
    return render_template("index.html", tickets=ticket_details, disruptions=disruptions, ticket_pairs=ticket_pairs)


@app.route("/add", methods=["POST"])
def add_maintenance():
    ticket_number = request.form.get("ticket_number", "").strip()
    start_str = request.form.get("start_time", "").strip()
    end_str = request.form.get("end_time", "").strip()
    main_str = request.form.get("main_services", "").strip()
    backup_str = request.form.get("backup_services", "").strip()

    if not ticket_number or not start_str or not end_str:
        flash("Ticket number, start time, and end time are required.", "error")
        return redirect(url_for("index"))

    try:
        start_time = parse_time(start_str)
        end_time = parse_time(end_str)
    except ValueError:
        flash("Invalid time format. Use: DD.MM.YYYY HH:MM UTC", "error")
        return redirect(url_for("index"))

    if end_time <= start_time:
        flash("End time must be after start time.", "error")
        return redirect(url_for("index"))

    main_services = extract_service_ids(main_str)
    backup_services = extract_service_ids(backup_str)

    if not main_services and not backup_services:
        flash("At least one affected service is required.", "error")
        return redirect(url_for("index"))

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO maintenance (ticket_number, start_time, end_time) VALUES (?, ?, ?)",
            (ticket_number, start_time.isoformat(), end_time.isoformat()),
        )
        m_id = cursor.lastrowid
        for sid in main_services:
            conn.execute(
                "INSERT INTO affected_paths (maintenance_id, service_id, path_type) VALUES (?, ?, 'main')",
                (m_id, sid),
            )
        for sid in backup_services:
            conn.execute(
                "INSERT INTO affected_paths (maintenance_id, service_id, path_type) VALUES (?, ?, 'backup')",
                (m_id, sid),
            )
        conn.commit()
        flash(f"Ticket {ticket_number} added.", "success")
    except sqlite3.IntegrityError:
        flash(f"Ticket {ticket_number} already exists.", "error")
    finally:
        conn.close()

    return redirect(url_for("index"))


@app.route("/add_note", methods=["POST"])
def add_note():
    service_id = request.form.get("service_id", "").strip()
    message = request.form.get("message", "").strip()
    if service_id and message:
        conn = get_db()
        conn.execute(
            "INSERT INTO disruption_notes (service_id, message) VALUES (?, ?)",
            (service_id, message),
        )
        conn.commit()
        conn.close()
    return redirect(url_for("index"))


@app.route("/delete/<int:maintenance_id>", methods=["POST"])
def delete_maintenance(maintenance_id):
    conn = get_db()
    conn.execute("DELETE FROM maintenance WHERE id = ?", (maintenance_id,))
    conn.commit()
    conn.close()
    flash("Ticket deleted.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
