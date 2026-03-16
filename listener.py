import time
import subprocess
import os
import datetime
import threading
import sqlite3
import json

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.expanduser("~/.wacli/wacli.db")
queue_dir = os.path.join(script_dir, 'queue')

print("Starting WhatsApp Listener Daemon for AI Artist (Polling sync mode)...", flush=True)

# Run wacli sync periodically in the background to keep the DB populated
def run_sync():
    while True:
        subprocess.run(["wacli", "sync"], capture_output=True)
        time.sleep(30)

threading.Thread(target=run_sync, daemon=True).start()

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

# Main polling loop
while True:
    time.sleep(5)
    
    # 1. Check for incoming WhatsApp messages
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            c = conn.cursor()
            c.execute("SELECT ts, text, chat_jid FROM messages WHERE ts > ? ORDER BY ts ASC;", (last_ts,))
            rows = c.fetchall()
            for row in rows:
                ts, text, sender = row
                last_ts = max(last_ts, ts)
                
                if text and "Here is your generated art!" not in text and "I have successfully implemented" not in text:
                    print(f"[{datetime.datetime.now()}] Detected trigger: {text[:30]}...", flush=True)
                    env = os.environ.copy()
                    env["MUSE_TEXT"] = text
                    env["SENDER_JID"] = sender
                    subprocess.Popen(["/home/nukebox/.openclaw/workspace/digital-art-engine/venv/bin/python3", os.path.join(script_dir, "main.py")], env=env)
    except Exception as e:
        print(f"DB Poll error: {e}", flush=True)

    # 2. Check queue for files to send
    for filename in os.listdir(queue_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(queue_dir, filename)
            try:
                with open(filepath, "r") as f:
                    req = json.load(f)
                
                print(f"Sending queued art: {req['gif_file']}", flush=True)
                cmd = ["wacli", "send", "file", "--to", req["sender_jid"], "--file", req["gif_file"], "--caption", req["caption"]]
                subprocess.run(cmd)
                os.remove(filepath)
            except Exception as e:
                print(f"Delivery failed: {e}", flush=True)
