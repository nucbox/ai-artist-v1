import time
import subprocess
import os
import datetime
import threading
import sqlite3

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.expanduser("~/.wacli/wacli.db")

print("Starting WhatsApp Listener Daemon for AI Artist (SQLite poll mode)...")

def run_pipeline(text, sender_jid):
    # Pass text to main.py via environment variables
    env = os.environ.copy()
    env["MUSE_TEXT"] = text
    env["SENDER_JID"] = sender_jid
    subprocess.run(["/home/nukebox/.openclaw/workspace/digital-art-engine/venv/bin/python3", os.path.join(script_dir, "main.py")], env=env)

# Run wacli sync --follow in the background to keep the DB populated
sync_process = subprocess.Popen(
    ["wacli", "sync", "--follow"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

# Get the initial highest timestamp so we don't process old messages
last_ts = 0
try:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        c = conn.cursor()
        c.execute("SELECT MAX(ts) FROM messages;")
        row = c.fetchone()
        if row and row[0]:
            last_ts = row[0]
except Exception as e:
    print(f"Initial DB connection error: {e}")

print(f"Listening for messages after timestamp: {last_ts}...")

# Poll the DB
while True:
    time.sleep(2)
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            c = conn.cursor()
            c.execute("SELECT ts, text, chat_jid FROM messages WHERE ts > ? ORDER BY ts ASC;", (last_ts,))
            rows = c.fetchall()
            for row in rows:
                ts, text, sender = row
                last_ts = max(last_ts, ts)
                
                if text and "Here is your generated art!" not in text and "I have successfully implemented the v0.0.1" not in text:
                    print(f"[{datetime.datetime.now()}] New message detected: {text}")
                    threading.Thread(target=run_pipeline, args=(text, sender)).start()
    except Exception as e:
        print(f"DB Poll error: {e}")
