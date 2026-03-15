import sqlite3
import os
import time

db_path = os.path.expanduser("~/.wacli/wacli.db")
with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
    c = conn.cursor()
    c.execute("SELECT ts, text, chat_jid FROM messages ORDER BY ts DESC LIMIT 1;")
    row = c.fetchone()
    print("Latest:", row)
