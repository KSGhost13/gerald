import json
import sqlite3
from .config import DATA

class Storage:
    def __init__(self, path=None):
        self.db = sqlite3.connect(path or DATA / 'gerald.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, time REAL, payload TEXT)')

    def get(self, key, default):
        row = self.db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (key, json.dumps(value)))

    def event(self, event):
        with self.db:
            self.db.execute('INSERT INTO events(time,payload) VALUES (?,?)', (event['time'], json.dumps(event)))
            self.db.execute('DELETE FROM events WHERE id <= (SELECT COALESCE(MAX(id),0)-5000 FROM events)')

    def recent(self):
        return [json.loads(r[0]) for r in reversed(self.db.execute('SELECT payload FROM events ORDER BY id DESC LIMIT 150').fetchall())]
