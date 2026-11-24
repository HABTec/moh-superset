#!/usr/bin/env python3
"""45_fix_stored_text.py - raise the contrast / minimum size of text stored inside chart definitions (Handlebars KPI cards,
markdown tables) on the REPLICA's metadata DB. Same substitutions as fix-handlebars-kpi.mjs, applied directly in SQL-free Python.
    45_fix_stored_text.py            dry run: counts only
    45_fix_stored_text.py --apply    writes; a JSON backup of every changed row goes to backups/chart-text-fix-<time>.json
Replica only (env: sstraining.env). Run on the server as sysadmin."""
import json, re, sys, time
ROOT = "/var/etls/moh-sstraining"; ENV = dict(l.rstrip("\n").split("=", 1) for l in open(f"{ROOT}/env/sstraining.env") if "=" in l)
import psycopg2
MAP = [
  (r"font-size:\s*clamp\(8px,\s*1\.4vh,\s*10px\)", "font-size:clamp(11px,1.4vh,12px)"),
  (r"font-size:\s*clamp\(8px,\s*1\.4vh,\s*11px\)", "font-size:clamp(11px,1.4vh,12px)"),
  (r"font-size:\s*clamp\(9px,\s*1\.6vh,\s*11px\)", "font-size:clamp(11px,1.6vh,12px)"),
  (r"font-size:\s*clamp\(10px,\s*2vh,\s*13px\)", "font-size:clamp(11px,2vh,13px)"),
  (r"font-size:\s*clamp\(10px,\s*2vh,\s*14px\)", "font-size:clamp(11px,2vh,14px)"),
  (r"color:\s*#6b7280", "color:#4b5563"), (r"color:\s*rgb\(\s*107,\s*114,\s*128\s*\)", "color:#4b5563"),
  (r"color:\s*#9ca3af", "color:#5b6472"),
  (r"font-size:\s*10px", "font-size:11px"),
  (r"(?<=\{\{else\}\})#6b7280", "#4b5563"), (r"(?<=\{\{else\}\})#9ca3af", "#5b6472"),   # conditional text colours
]
def fix(t):
    n = 0
    for pat, rep in MAP: t, k = re.subn(pat, rep, t, flags=re.I); n += k
    return t, n
pg = psycopg2.connect(host="127.0.0.1", port=5445, user="sst_admin", password=ENV["SST_PG_PASSWORD"], dbname="sst_superset"); cur = pg.cursor()
cur.execute("select id, slice_name, viz_type, params, query_context from slices")
changes = []
for id_, name, viz, params, qc in cur.fetchall():
    np_, a = fix(params or ""); nq, b = fix(qc or "")
    if a or b: changes.append((id_, name, viz, params, qc, np_, nq, a + b))
print(f"{len(changes)} charts contain text to fix; replacements: {sum(c[7] for c in changes)}")
for c in changes[:8]: print("  ", c[0], c[2], (c[1] or "")[:40], c[7])
if "--apply" in sys.argv and changes:
    bk = f"{ROOT}/backups/chart-text-fix-{time.strftime('%Y%m%d_%H%M%S')}.json"
    json.dump([{"id": c[0], "params": c[3], "query_context": c[4]} for c in changes], open(bk, "w")); import os; os.chmod(bk, 0o600)
    for c in changes: cur.execute("update slices set params=%s, query_context=%s, changed_on=now() where id=%s", (c[5], c[6] or None, c[0]))
    pg.commit(); print("applied; backup", bk)
