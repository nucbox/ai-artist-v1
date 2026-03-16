import time
import subprocess
import os
import datetime
import threading
import sqlite3

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.expanduser("~/.wacli/wacli.db")

print("Starting WhatsApp Listener Daemon for AI Artist (Polling sync mode)...", flush=True)

def run_pipeline(text, sender_jid):
    # Pass text to main.py via environment variables
    env = os.environ.copy()
    env["MUSE_TEXT"] = text
    env["SENDER_JID"] = sender_jid
    subprocess.run(["/home/nukebox/.openclaw/workspace/digital-art-engine/venv/bin/python3", os.path.join(script_dir, "main.py")], env=env)

# Initialize timestamp
last_ts = 0
try:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        c = conn.cursor()
        c.execute("SELECT MAX(ts) FROM messages;")
        row = c.fetchone()
        if row and row[0]:
            last_ts = row[0]
except Exception as e:
    print(f"Initial DB connection error: {e}", flush=True)

# Polling loop
while True:
    try:
        # Run sync synchronously (no background process locking the DB)
        subprocess.run(["wacli", "sync"], capture_output=True)
        
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            c = conn.cursor()
            c.execute("SELECT ts, text, chat_jid FROM messages WHERE ts > ? ORDER BY ts ASC;", (last_ts,))
            rows = c.fetchall()
            for row in rows:
                ts, text, sender = row
                last_ts = max(last_ts, ts)
                
                # Filter out system replies
                if text and "Here is your generated art!" not in text and "I have successfully implemented" not in text:
                    print(f"[{datetime.datetime.now()}] Detected trigger: {text[:30]}...", flush=True)
                    threading.Thread(target=run_pipeline, args=(text, sender)).start()
    except Exception as e:
        print(f"DB Poll error: {e}", flush=True)
    
    time.sleep(30) # Poll every 30 seconds
