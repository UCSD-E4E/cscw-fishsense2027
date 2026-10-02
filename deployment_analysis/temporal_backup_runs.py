"""Workflow runs from Temporal's own database backups (May 2026), for the older pipeline window.

Live Temporal keeps ~30 days, so earlier runs survive only in the nightly persistence backups
(`fishsense_process_work/database_backups_premove/temporal_db`, 2026-05-03 .. 05-13, copied to
~/.cache/cscw-fishsense2027/temporal_backups). The visibility database was not backed up, so
start/close times are decoded from each workflow's event history (`history_node`, Proto3
`temporal.api.history.v1.History` batches) with the Temporal SDK's protobufs.

Per workflow run (history tree): type, first and last event time, outcome (the closing event's
type), and the run's first input payload, which for per-dive workflows names the dive. Snapshots
overlap, so runs are de-duplicated by tree id, keeping the snapshot with the most events.

Needs a Postgres container `p2-temporal-old` with the dumps mounted at /d, and an environment with
`temporalio` (fishsense-lite's venv):
  ../../fishsense-lite/.venv/bin/python temporal_backup_runs.py  > ../data/temporal/workflow_runs_may2026.csv
"""
from __future__ import annotations

import csv, json, subprocess, sys
from pathlib import Path

from temporalio.api.enums.v1 import EventType
from temporalio.api.history.v1 import History

DUMPS = Path.home() / ".cache/cscw-fishsense2027/temporal_backups"
CLOSERS = {"EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED": "COMPLETED", "EVENT_TYPE_WORKFLOW_EXECUTION_FAILED": "FAILED",
           "EVENT_TYPE_WORKFLOW_EXECUTION_TIMED_OUT": "TIMED_OUT", "EVENT_TYPE_WORKFLOW_EXECUTION_CANCELED": "CANCELED",
           "EVENT_TYPE_WORKFLOW_EXECUTION_TERMINATED": "TERMINATED", "EVENT_TYPE_WORKFLOW_EXECUTION_CONTINUED_AS_NEW": "CONTINUED_AS_NEW"}


def psql(db, sql):
    return subprocess.run(["docker", "exec", "p2-temporal-old", "psql", "-U", "postgres", "-d", db, "-At", "-c", sql],
                          capture_output=True, text=True, check=True).stdout


def restore(dump):
    db = "t_" + dump.stem.replace("-", "_").replace("T", "_").replace("Z", "").lower()
    subprocess.run(["docker", "exec", "p2-temporal-old", "dropdb", "-U", "postgres", "--if-exists", db], check=True)
    subprocess.run(["docker", "exec", "p2-temporal-old", "createdb", "-U", "postgres", db], check=True)
    subprocess.run(["docker", "exec", "p2-temporal-old", "pg_restore", "-U", "postgres", "-d", db, "--no-owner",
                    "-t", "history_node", f"/d/{dump.name}"], capture_output=True)
    return db


def first_payload(started):
    for p in started.input.payloads:
        try:
            return json.dumps(json.loads(p.data.decode()))[:200]
        except Exception:
            return p.data[:200].decode(errors="replace")
    return ""


def runs_in(db):
    out = {}
    # hex, not base64: Postgres wraps base64 at 76 characters, which splits rows across lines
    rows = psql(db, "select encode(tree_id,'hex'), node_id, encode(data,'hex') from history_node order by tree_id, node_id")
    for line in rows.splitlines():
        tree, node, hx = line.split("|")
        h = History(); h.ParseFromString(bytes.fromhex(hx))
        r = out.setdefault(tree, dict(tree=tree, type="", start="", end="", status="OPEN", input="", events=0))
        for e in h.events:
            r["events"] += 1
            t = e.event_time.ToDatetime().isoformat() + "Z"
            name = EventType.Name(e.event_type)
            if name == "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED":
                a = e.workflow_execution_started_event_attributes
                r.update(type=a.workflow_type.name, start=t, input=first_payload(a))
            if name in CLOSERS:
                r.update(end=t, status=CLOSERS[name])
    return out


def main():
    best = {}
    for dump in sorted(DUMPS.glob("*.dump")):
        toc = subprocess.run(["docker", "exec", "p2-temporal-old", "pg_restore", "-l", f"/d/{dump.name}"],
                             capture_output=True, text=True).stdout
        if "dbname: temporal_db" not in toc or "history_node" not in toc:
            print(f"{dump.name}: not a Temporal persistence dump, skipped", file=sys.stderr, flush=True)
            continue    # 2026-05-03T06-52-46Z in that folder is a fishsense database dump
        db = restore(dump)
        for tree, r in runs_in(db).items():
            if tree not in best or r["events"] > best[tree]["events"]:
                best[tree] = r
        subprocess.run(["docker", "exec", "p2-temporal-old", "dropdb", "-U", "postgres", db], check=True)
        print(f"{dump.name}: {len(best)} runs so far", file=sys.stderr, flush=True)
    w = csv.writer(sys.stdout); w.writerow(["workflow_type", "start_time", "close_time", "status", "input"])
    for r in sorted(best.values(), key=lambda r: r["start"]):
        if r["type"]:
            w.writerow([r["type"], r["start"], r["end"], r["status"], r["input"]])


if __name__ == "__main__":
    main()
