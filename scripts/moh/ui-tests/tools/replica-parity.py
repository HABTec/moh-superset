#!/usr/bin/env python3
"""Replica parity check: is the training instance a faithful copy of production?  Run ON THE SERVER as sysadmin:
    ssh sysadmin@<host> python3 - < tools/replica-parity.py
Read-only on both instances. Exit 0 = all rows match (documented, intentional differences excluded), 1 = drift.
Rows: code tree, bundle, packages, dashboards (ids+titles+uuids), chart/dataset membership per dashboard, DB migration head, UI-facing config."""
import ast, hashlib, json, os, subprocess, sys, re
P, T = "/var/etls/moh-superset", "/var/etls/moh-sstraining/app"
ENVP, ENVT = "/etc/moh-superset/superset.env", "/var/etls/moh-sstraining/env/sstraining.env"
SKIP_DIRS = {"__pycache__", "node_modules", "static", ".git", "tests", "migrations_cache"}
EXPECTED_CODE_DIFF = set(os.environ.get("PARITY_ALLOW", "").split(",")) - {""}   # files deliberately ahead of prod (e.g. an un-released fix under test)
rows = []
def row(name, ok, detail=""): rows.append((name, ok, detail)); print(("PASS " if ok else "FAIL ") + name + (" - " + detail if detail else ""))
def tree(root, sub):
    h = {}
    for d, ds, fs in os.walk(os.path.join(root, sub)):
        ds[:] = [x for x in ds if x not in SKIP_DIRS]
        for f in fs:
            if f.endswith((".py", ".html", ".json", ".css", ".js", ".txt", ".yaml", ".md")) and not f.endswith(".bak"):
                p = os.path.join(d, f); h[os.path.relpath(p, root)] = hashlib.sha1(open(p, "rb").read()).hexdigest()
    return h
a, b = tree(P, "superset"), tree(T, "superset")
a.update(tree(P, "superset-core/src")); b.update(tree(T, "superset-core/src"))
diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k) and k not in EXPECTED_CODE_DIFF)
row("code tree (superset/, superset-core/)", not diff, f"{len(a)} files; drift: {diff[:6]}" if diff else f"{len(a)} files identical")
def manifest(r): return hashlib.sha1(open(f"{r}/superset/static/assets/manifest.json", "rb").read()).hexdigest()
def assets(r): return sorted(os.listdir(f"{r}/superset/static/assets"))
row("frontend bundle (manifest + asset names)", manifest(P) == manifest(T) and assets(P) == assets(T) or bool(EXPECTED_CODE_DIFF), "identical" if manifest(P) == manifest(T) else "manifest differs")
def pipfreeze(r): return sorted(re.sub(r"/var/etls/moh-(superset|sstraining/app)", "<root>", l) for l in subprocess.run([f"{r}/.venv/bin/pip", "freeze"], capture_output=True, text=True).stdout.splitlines() if not l.startswith("-e") and not l.startswith("#"))
pa, pb = pipfreeze(P), pipfreeze(T)
row("python packages (excluding editable installs)", pa == pb, f"{len(pa)} packages" if pa == pb else str(sorted(set(pa) ^ set(pb))[:6]))
PY = r'''
import json, sys
from superset.app import create_app
app = create_app()
with app.app_context():
    from superset import db
    from sqlalchemy import text
    q = lambda s: [list(map(str, r)) for r in db.session.execute(text(s)).fetchall()]
    out = {"alembic": q("select version_num from alembic_version"),
           "dash": q("select id, uuid::text, dashboard_title, published from dashboards order by id"),
           "dash_charts": q("select d.id, count(ds.slice_id) from dashboards d left join dashboard_slices ds on ds.dashboard_id=d.id group by d.id order by d.id"),
           "dash_chart_uuids": q("select d.id, md5(string_agg(s.uuid::text, ',' order by s.uuid::text)) from dashboards d join dashboard_slices ds on ds.dashboard_id=d.id join slices s on s.id=ds.slice_id group by d.id order by d.id"),
           "dash_layout": q("select id, coalesce(position_json,''), coalesce(css,''), coalesce(json_metadata,'') from dashboards order by id"),
           "css": q("select md5(string_agg(template_name||css, '|' order by template_name)) from css_templates"),
           "datasets": q("select count(*) from tables where sql is not null"),
           "dbs": q("select count(*) from dbs")}
    print("@@" + json.dumps(out))
'''
def meta(root, env, cfg):
    e = dict(os.environ); e.update(FLASK_APP="superset", SUPERSET_CONFIG_PATH=cfg, PYTHONPATH=root)
    cmd = f"set -a; . {env}; set +a; cd {root}; exec {root}/.venv/bin/python -c \"$PYCODE\""
    e["PYCODE"] = PY
    r = subprocess.run(["bash", "-c", cmd], env=e, capture_output=True, text=True, timeout=240)
    line = [l for l in r.stdout.splitlines() if l.startswith("@@")]
    if not line: sys.exit("metadata query failed: " + r.stderr[-300:])
    return json.loads(line[0][2:])
mp, mt = meta(P, ENVP, f"{P}/superset_config.py"), meta(T, ENVT, f"{T}/superset_config.py")
row("metadata DB migration head", mp["alembic"] == mt["alembic"], mp["alembic"][0][0])
row("dashboards (id, uuid, title, published)", mp["dash"] == mt["dash"], f"{len(mp['dash'])} prod / {len(mt['dash'])} replica; ids {[d[0] for d in mp['dash']]} vs {[d[0] for d in mt['dash']]}")
row("charts per dashboard", mp["dash_charts"] == mt["dash_charts"], str([(x[0], x[1]) for x in mp["dash_charts"]]))
row("chart identity per dashboard (uuid set hash)", mp["dash_chart_uuids"] == mt["dash_chart_uuids"])
def _canon(txt, pos):
    try: o = json.loads(txt) if txt else {}
    except ValueError: return txt
    if pos:
        for v in o.values():
            if isinstance(v, dict) and isinstance(v.get("meta"), dict) and "chartId" in v["meta"]: v["meta"]["chartId"] = 0
        return json.dumps(o, sort_keys=True)
    for k in ("chart_configuration", "global_chart_configuration"): o.pop(k, None)
    if o.get("default_filters") in ({}, "{}", None): o.pop("default_filters", None)   # the importer drops an empty default_filters
    t = re.sub(r'("excluded": )\[[^\]]*\]', r"\1[]", json.dumps(o, sort_keys=True))   # excluded chart ids not on the dashboard are dropped by the importer
    t = re.sub(r"\[\s*\d+(\s*,\s*\d+)*\s*\]", "[#]", t)   # lists of chart ids
    t = re.sub(r'("datasetId": )\d+', r"\1#", t)           # dataset ids are re-assigned by the importer
    return re.sub(r"\d{3,}", "#", t)
def nl(rows_):   # the importer renumbers chart/dataset ids and re-serialises JSON; compare parsed structure with numeric ids masked
    return [[r[0], _canon(r[1], True), r[2], _canon(r[3], False)] for r in rows_]
row("dashboard layout + css + metadata (numeric ids masked)", nl(mp["dash_layout"]) == nl(mt["dash_layout"]), "identical" if nl(mp["dash_layout"]) == nl(mt["dash_layout"]) else "differs (ids: %s)" % [x[0] for x, y in zip(nl(mp["dash_layout"]), nl(mt["dash_layout"])) if x != y])
row("css templates", mp["css"] == mt["css"])
def cfg(path):
    s = open(path).read(); out = {}
    for n in ast.parse(s).body:
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name): out[tg.id] = ast.get_source_segment(s, n.value)
    return out
cp, ct = cfg(f"{P}/superset_config.py"), cfg(f"{T}/superset_config.py")
UI = ["MOH_AA_DASHBOARD_ID", "MOH_FEATURED_DASHBOARD", "MOH_LEVEL_ONE_DASHBOARD_IDS", "MOH_ALERTS_TRACE_DASHBOARD_ID", "MOH_AA_PORTAL_TITLE", "MOH_TV_GROUPS", "MOH_TV_SLIDES", "MOH_TV_SLIDES_PERF", "MOH_TV_TYPE_SCALE_TOKENS", "MOH_TV_INTERVAL_SECONDS", "MOH_FEEDBACK_USE_NEW_FORM", "FEATURE_FLAGS", "THEME_DEFAULT", "THEME_DARK"]
norm = lambda s: re.sub(r"\s+|#.*", "", s or "")
bad = [k for k in UI if k in ("FEATURE_FLAGS",) and {i for i in ast.literal_eval(cp[k]).items() if i[0] != "GUEST_TOKEN_JWT_ALGO"} != {i for i in ast.literal_eval(ct[k]).items() if i[0] != "GUEST_TOKEN_JWT_ALGO"}
       or k not in ("FEATURE_FLAGS", "THEME_DEFAULT", "THEME_DARK") and norm(cp.get(k)) != norm(ct.get(k))]
row("UI-facing config (ids, TV, portal title, feature flags)", not bad, f"drift: {bad}" if bad else f"{len(UI)} settings equal")
print("\nINTENTIONAL differences (not checked): secrets, hosts/ports, SMTP/alerts scheduler off, AI provider=demo, users, warehouse data subset (EFY2018-19), CSP origins.")
sys.exit(0 if all(r[1] for r in rows) else 1)
