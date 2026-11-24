#!/usr/bin/env python3
"""43_usage_synth.py - recreate moh_superset_usage (5 tables the Usage dashboard reads) on the REPLICA ClickHouse with MASKED data.
READ-ONLY on production (SELECT, local default user). Masking: username/email/first_name/last_name replaced by values derived from user_id,
email-looking text in error_message/subject removed. Rows: all of dim_users, alert runs/emails, dashboard visits; the newest 150k usage events.
Idempotent (tables dropped and recreated). Run on the server as sysadmin."""
import subprocess, sys
ENV = dict(l.rstrip("\n").split("=", 1) for l in open("/var/etls/moh-sstraining/env/sstraining.env") if "=" in l)
DST = ["clickhouse-client", "--host", "127.0.0.1", "--port", "19033", "--user", "training_admin", "--password", ENV["SST_CH_ADMIN_PASSWORD"]]
SRC = ["clickhouse-client"]
def run(cmd, q, inp=None):
    p = subprocess.run(cmd + ["-q", q], input=inp, capture_output=True)
    if p.returncode: sys.exit("FAILED: " + q[:100] + "\n" + p.stderr.decode()[:400])
    return p.stdout
DB = "moh_superset_usage"
EM = "'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+'"
def mask(cols):
    r = []
    uid = "user_id" if "user_id" in cols else "cityHash64(ifNull(username, ifNull(email, '')))"
    if "username" in cols: r.append(f"CAST(concat('user', toString({uid})) AS Nullable(String)) AS username")
    if "email" in cols: r.append(f"CAST(concat('user', toString({uid}), '@example.invalid') AS Nullable(String)) AS email")
    if "first_name" in cols: r.append("CAST('Trainee' AS Nullable(String)) AS first_name")
    if "last_name" in cols: r.append(f"CAST(concat('U', toString({uid})) AS Nullable(String)) AS last_name")
    for c in ("error_message", "subject"):
        if c in cols: r.append(f"CAST(replaceRegexpAll(ifNull({c}, ''), {EM}, 'user@example.invalid') AS Nullable(String)) AS {c}")
    return "SELECT * REPLACE (" + ", ".join(r) + ")" if r else "SELECT *"
TABLES = {"dim_users": "", "fct_alert_emails": "", "fct_alert_runs": "", "fct_dashboard_visits": "", "fct_usage_events": "ORDER BY event_time_utc DESC LIMIT 150000"}
run(DST, f"CREATE DATABASE IF NOT EXISTS {DB}")
for t, tail in TABLES.items():
    cols = run(SRC, f"SELECT name FROM system.columns WHERE database='{DB}' AND table='{t}' FORMAT TSV").decode().split()
    ddl = run(SRC, f"SHOW CREATE TABLE {DB}.{t} FORMAT TSVRaw").decode()
    run(DST, f"DROP TABLE IF EXISTS {DB}.{t}"); run(DST, ddl)
    if t.startswith("fct_alert") or t == "dim_users":
        sel = mask(cols) + f" FROM {DB}.{t} {tail}"
    else:
        sel = mask(cols) + f" FROM {DB}.{t} {tail}"
    data = run(SRC, sel + " FORMAT Native")
    run(DST, f"INSERT INTO {DB}.{t} FORMAT Native", inp=data)
    print(t, run(DST, f"SELECT count() FROM {DB}.{t}").decode().strip())
run(DST, f"GRANT SELECT ON {DB}.* TO participant")
print("granted SELECT on", DB, "to participant")
