#!/usr/bin/env python3
"""44_parity_import.py - make the REPLICA's dashboards an exact copy of production's, INCLUDING production's dashboard ids.
Input : data/parity/prod_export.zip (superset export-dashboards on prod) + data/parity/prod_meta.json (id/uuid/title, css templates).
Does  : (1) removes every dashboard on the replica (+ report schedules / welcome-page refs that block it)  [pg_dump backup taken first]
        (2) for each prod dashboard, in id order: sets the id sequence so the import creates that exact id, imports a single-dashboard bundle
        (3) copies css templates.   DB connections are rewritten to the replica (participant read-only user); Usage DB -> replica moh_superset_usage.
Run on the server as sysadmin. Prod is never touched here."""
import glob, json, os, shutil, subprocess, sys, tempfile, zipfile, yaml, re
ROOT = "/var/etls/moh-sstraining"; D = f"{ROOT}/data/parity"
ENV = dict(l.rstrip("\n").split("=", 1) for l in open(f"{ROOT}/env/sstraining.env") if "=" in l)
REPLICA_UUID = "7d1f2a54-5f0e-4c43-9d34-5a7c1d0b7e02"
sys.path.insert(0, f"{ROOT}/app")
import psycopg2
pg = psycopg2.connect(host="127.0.0.1", port=5445, user="sst_admin", password=ENV["SST_PG_PASSWORD"], dbname="sst_superset"); pg.autocommit = True
cur = pg.cursor()
meta = json.load(open(f"{D}/prod_meta.json"))
z = zipfile.ZipFile(f"{D}/prod_export.zip"); names = z.namelist(); root = names[0].split("/")[0]
Y = {n: yaml.safe_load(z.read(n)) for n in names if n.endswith(".yaml")}
by = lambda kind: {y["uuid"]: (n, y) for n, y in Y.items() if f"/{kind}/" in n and "uuid" in y}
dashboards, charts, datasets, databases = by("dashboards"), by("charts"), by("datasets"), by("databases")
def rewrite_db(y):
    y = dict(y); y["allow_file_upload"] = False; y["allow_dml"] = False; y.pop("password", None)
    if "usage" in y["database_name"].lower():
        y["sqlalchemy_uri"] = f"clickhousedb://participant:{ENV['SST_CH_PARTICIPANT_PASSWORD']}@127.0.0.1:18133/moh_superset_usage"
    else:
        y["uuid"] = REPLICA_UUID
        y["sqlalchemy_uri"] = f"clickhousedb://participant:{ENV['SST_CH_PARTICIPANT_PASSWORD']}@127.0.0.1:18133/training"
    return y
dbmap = {u: rewrite_db(y)["uuid"] for u, (n, y) in databases.items()}
print("1) removing replica dashboards")
cur.execute("select conrelid::regclass::text, (select attname from pg_attribute where attrelid=conrelid and attnum=conkey[1]) from pg_constraint where confrelid='report_schedule'::regclass")
for t, c in cur.fetchall(): cur.execute(f"delete from {t} where {c} in (select id from report_schedule where dashboard_id is not null)")
cur.execute("delete from report_schedule where dashboard_id is not null"); cur.execute("update user_attribute set welcome_dashboard_id=null where welcome_dashboard_id is not null")
cur.execute("delete from dashboards"); print("   dashboards left:", cur.execute("select count(*) from dashboards") or cur.fetchone()[0])
env = {**os.environ, **ENV, "SUPERSET_CONFIG_PATH": f"{ROOT}/app/superset_config.py", "FLASK_APP": "superset", "PYTHONPATH": f"{ROOT}/app", "SST_FORCE_HTTPS": "false", "PATH": f"{ROOT}/app/.venv/bin:" + os.environ["PATH"]}
rc = 0
for pid, puuid, title, slug, published in meta["dashboards"]:
    dn, dy = dashboards[puuid]; text = yaml.safe_dump(dy)
    uu = set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text))
    ch = {u for u in charts if u in uu}; ds = {charts[u][1]["dataset_uuid"] for u in ch} | {u for u in datasets if u in uu}
    db_ = {datasets[u][1]["database_uuid"] for u in ds}
    tmp = tempfile.mkdtemp(dir=D); os.chmod(tmp, 0o700)
    def put(n, y): p = os.path.join(tmp, n); os.makedirs(os.path.dirname(p), exist_ok=True); yaml.safe_dump(y, open(p, "w"), allow_unicode=True)
    put(f"{root}/metadata.yaml", Y[f"{root}/metadata.yaml"]); put(dn, dy)
    for u in ch: put(*[charts[u][0], charts[u][1]])
    for u in ds:
        n, y = datasets[u]; y = dict(y); y["database_uuid"] = dbmap[y["database_uuid"]]; put(n, y)
    for u in db_:
        n, y = databases[u]; put(n, rewrite_db(y))
    out = f"{tmp}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zz:
        for p in glob.glob(tmp + "/**", recursive=True):
            if os.path.isfile(p): zz.write(p, os.path.relpath(p, tmp))
    shutil.rmtree(tmp); os.chmod(out, 0o600)
    cur.execute("select setval('dashboards_id_seq', %s, false)", (pid,))
    r = subprocess.run([f"{ROOT}/app/.venv/bin/python", "-c", "from superset.cli.main import superset as s; s()", "import-dashboards", "-p", out, "-u", "admin"], env=env, capture_output=True, text=True, cwd=f"{ROOT}/app")
    os.remove(out)
    cur.execute("select id from dashboards where uuid=%s", (puuid,)); got = cur.fetchone()
    ok = bool(got) and got[0] == pid; rc |= (not ok)
    print(f"2) prod id {pid:>2} {title[:34]:34} charts={len(ch):>3} datasets={len(ds):>3} -> replica id {got[0] if got else None} {'OK' if ok else 'MISMATCH'}")
    if not ok: print((r.stdout + r.stderr)[-800:])
cur.execute("select setval('dashboards_id_seq', (select max(id) from dashboards))")
print("3) css templates")
cur.execute("delete from css_templates")
for name, css in meta["css"]: cur.execute("insert into css_templates (template_name, css, created_on, changed_on) values (%s,%s,now(),now())", (name, css))
cur.execute("select count(*) from dashboards"); print("dashboards:", cur.fetchone()[0]); cur.execute("select count(*) from css_templates"); print("css_templates:", cur.fetchone()[0])
sys.exit(rc)
