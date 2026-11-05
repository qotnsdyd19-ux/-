"""Local research workspace; approvals are never accepted from uploaded files."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from src.data import frame

class Store:
    def __init__(self,path='artifacts/workspace.sqlite'):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.path=str(path)
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS audit (time TEXT, id TEXT, payload TEXT)')
    def connect(self): return sqlite3.connect(self.path)
    def add(self,df):
        added=0
        with self.connect() as c:
            for row in json.loads(df.to_json(orient='records')):
                added+=c.execute('INSERT OR IGNORE INTO records VALUES (?,?)',(row['record_id'],json.dumps(row,ensure_ascii=False))).rowcount
        return added
    def records(self):
        with self.connect() as c: rows=c.execute('SELECT payload FROM records ORDER BY id').fetchall()
        return frame([json.loads(r[0]) for r in rows])
    def reviews(self):
        with self.connect() as c: rows=c.execute('SELECT id,payload FROM reviews').fetchall()
        return {k:json.loads(v) for k,v in rows}
    def review(self,record_id,review):
        if not review.get('reviewer','').strip() or not review.get('evidence','').strip(): raise ValueError('검토자와 원문 근거를 입력하세요.')
        review['reviewed_at']=datetime.now(timezone.utc).isoformat()
        payload=json.dumps(review,ensure_ascii=False)
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO reviews VALUES (?,?)',(record_id,payload))
            c.execute('INSERT INTO audit VALUES (?,?,?)',(review['reviewed_at'],record_id,payload))
