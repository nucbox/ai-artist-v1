import time
import subprocess
import os
import json
import datetime

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
state_file = os.path.join(script_dir, 'last_run.txt')

def get_last_run():
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            return f.read().strip()
    return "2000-01-01T00:00:00Z"

print("Starting WhatsApp Listener Daemon for AI Artist...")

while True:
    last_run = get_last_run()
    # Check for new messages
    cmd = ["wacli", "messages", "search", "", "--limit", "1", "--json", "--after", last_run[:10]]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            messages = json.loads(res.stdout)
            if messages:
                msg = messages[0]
                user_text = msg.get('text', '')
                if user_text:
                    print(f"[{datetime.datetime.now()}] New message detected: {user_text}")
                    # Run the pipeline
                    subprocess.run(["/home/nukebox/.openclaw/workspace/digital-art-engine/venv/bin/python3", os.path.join(script_dir, "main.py")])
    except Exception as e:
        print(f"Error checking messages: {e}")
        
    time.sleep(10)
