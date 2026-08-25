import sqlite3

con = sqlite3.connect(r"d:\work\project\20260806\model_train\backend\llm_train.db")
cur = con.cursor()
tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table'").fetchall()]
print("tables:", tables)
for t in ("models", "model_versions", "model_files", "users"):
    if t in tables:
        cols = [(c[1], c[2]) for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
        n = cur.execute(f"select count(*) from {t}").fetchone()[0]
        print(f"{t} cols({len(cols)}):", cols)
        print(f"{t} rows:", n)
con.close()
