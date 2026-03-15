import time
import subprocess
import os
import json
import datetime
import threading

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))

print("Starting WhatsApp Listener Daemon for AI Artist...")

def run_pipeline(text, sender_jid):
    # Pass text to main.py via environment variables
    env = os.environ.copy()
    env["MUSE_TEXT"] = text
    env["SENDER_JID"] = sender_jid
    subprocess.run(["/home/nukebox/.openclaw/workspace/digital-art-engine/venv/bin/python3", os.path.join(script_dir, "main.py")], env=env)

# Run wacli sync --follow
process = subprocess.Popen(
    ["wacli", "sync", "--follow", "--json"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

for line in iter(process.stdout.readline, ''):
    line = line.strip()
    if not line or line == "Connected.":
        continue
    try:
        data = json.loads(line)
        # Check if it's a message event
        if "messages" in data:
            for msg in data["messages"]:
                if msg.get("FromMe") is False:
                    text = msg.get("Text", "")
                    sender = msg.get("ChatJID", "")
                    if text:
                        print(f"[{datetime.datetime.now()}] New message detected: {text}")
                        # trigger pipeline in background so we don't block the listener
                        threading.Thread(target=run_pipeline, args=(text, sender)).start()
    except Exception as e:
        # Not JSON or parsing error
        pass
