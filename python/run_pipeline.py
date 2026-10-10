"""Load raw parquet into DuckDB, build the clean layer, run every named query in sql/ and export results to outputs/.

Usage:  python python/run_pipeline.py
"""
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA, SQL, OUT = ROOT / "data", ROOT / "sql", ROOT / "outputs"
OUT.mkdir(exist_ok=True)

RAW = {"raw_users": "users", "raw_events": "events", "raw_subscriptions": "subscriptions",
       "raw_experiment_assignments": "experiment_assignments", "raw_support_tickets": "support_tickets"}

con = duckdb.connect(str(DATA / "tasklane.duckdb"))
for table, f in RAW.items():
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{(DATA / (f + '.parquet')).as_posix()}')")
    print(f"loaded {table:28s} {con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:>10,} rows")

con.execute((SQL / "00_clean.sql").read_text(encoding="utf8"))
print("clean layer built")

pattern = re.compile(r"^-- name:\s*(\w+)\s*$", re.M)
for path in sorted(SQL.glob("0[1-9]_*.sql")):
    text = path.read_text(encoding="utf8")
    marks = list(pattern.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        query = text[m.end():end].strip().rstrip(";")
        df = con.execute(query).df()
        df.to_csv(OUT / f"{m.group(1)}.csv", index=False)
        print(f"{path.name:24s} {m.group(1):34s} {len(df):>7,} rows")
con.close()
