import os
import subprocess
import json
import datetime
import asyncio
from playwright.async_api import async_playwright
import imageio.v3 as iio
from google import genai

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
gallery_dir = os.path.join(script_dir, 'gallery')
state_file = os.path.join(script_dir, 'last_run.txt')
os.makedirs(gallery_dir, exist_ok=True)

# The user's whatsapp chat ID or name for getting inspiration
WA_CHAT = "Art Ideas"

# The design patterns to enforce
PATTERNS = """
Use complex easing functions like easeInOutQuint, restrict color palettes to 4-5 vivid hex codes,
utilize object-oriented classes with asynchronous animation states, avoid pure randomness in favor
of noise or grid-anchored offsets. Make it look like a professional p5.js generative art piece.
"""

gemini_client = genai.Client()

def get_last_run():
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            return f.read().strip()
    return "2000-01-01T00:00:00Z"

def save_last_run():
    with open(state_file, 'w') as f:
        f.write(datetime.datetime.utcnow().isoformat() + "Z")

def ask_gemini(prompt):
    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text.strip()

def get_muse_prompt():
    if "MUSE_TEXT" in os.environ:
        user_text = os.environ["MUSE_TEXT"]
        sender_jid = os.environ.get("SENDER_JID", "")
        print(f"Received user message from listener: {user_text}")
        try:
            expanded = ask_gemini(f"Act as an avant-garde digital art director. Take this raw idea: '{user_text}' and expand it into a rich generative art prompt. Return ONLY the prompt text.")
            if expanded:
                return expanded, sender_jid
        except Exception as e:
            print(f"Gemini API error: {e}")
        return user_text, sender_jid

    last_run = get_last_run()
    print(f"Checking for new messages since {last_run}...")
    
    # Check for new whatsapp messages
    try:
        cmd = ["wacli", "messages", "search", "", "--limit", "1", "--json", "--after", last_run[:10]]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            # Try to parse output. The skill doc doesn't guarantee exact structure, so we just use the text.
            messages = json.loads(res.stdout)
            if messages:
                # Find the most recent message since last_run
                msg = messages[0]
                user_text = msg.get('text', '')
                sender_jid = msg.get('chatJid', '') or msg.get('sender', '')
                if not sender_jid and 'key' in msg and 'remoteJid' in msg['key']:
                    sender_jid = msg['key']['remoteJid']
                
                if user_text:
                    print(f"Found user message: {user_text} from {sender_jid}")
                    try:
                        expanded = ask_gemini(f"Act as an avant-garde digital art director. Take this raw idea: '{user_text}' and expand it into a rich generative art prompt. Return ONLY the prompt text.")
                        if expanded:
                            return expanded, sender_jid
                    except Exception as e:
                        print(f"Gemini API error: {e}")
    except Exception as e:
        print(f"Warning: WhatsApp fetch failed: {e}")
        
    # Autonomous mode
    print("No new messages found. Running autonomous brainstorming...")
    try:
        expanded = ask_gemini("Act as an avant-garde digital art director. Generate a highly creative generative art concept based on nature, current digital trends, or mathematics. Return ONLY the text description of the concept.")
        if expanded:
            return expanded, None
    except Exception as e:
        print(f"Gemini API error: {e}")
    return "A complex geometric landscape of rippling cubes in neon green and deep purple.", None

def generate_code(prompt):
    print("Generating code from concept...")
    sys_prompt = f"You are an expert generative artist writing p5.js code. The concept is: {prompt}. Apply these patterns strictly: {PATTERNS}. Return ONLY the raw HTML string containing the complete p5.js sketch. No markdown fences, no explanations."
    try:
        html = ask_gemini(sys_prompt)
        if html.startswith("```html"):
            html = html[7:]
        if html.endswith("```"):
            html = html[:-3]
        return html.strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        return ""

async def render_gif(html_code):
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save the generated code alongside the GIF
    code_filename = os.path.join(gallery_dir, f"ai_art_{timestamp}.html")
    with open(code_filename, "w") as f:
        f.write(html_code)
        
    html_path = os.path.join(script_dir, "dynamic_canvas.html")
    with open(html_path, "w") as f:
        f.write(html_code)
    
    print("Rendering with Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{html_path}")
        
        frames = []
        for i in range(60):
            path = os.path.join(script_dir, f"frame_{i:03d}.png")
            await page.screenshot(path=path)
            frames.append(iio.imread(path))
            os.remove(path)
            await asyncio.sleep(0.05)
            
        filename = os.path.join(gallery_dir, f"ai_art_{timestamp}.gif")
        iio.imwrite(filename, frames, duration=50, loop=0)
        print(f"Artwork saved: {filename}")
        print(f"Code saved: {code_filename}")
        await browser.close()
        return filename

if __name__ == "__main__":
    concept, sender_jid = get_muse_prompt()
    print(f"CONCEPT:\n{concept}\n")
    
    html_code = generate_code(concept)
    if not html_code:
        print("Failed to generate code.")
        exit(1)
        
    gif_file = asyncio.run(render_gif(html_code))
    
    if sender_jid:
        print(f"Sending back to {sender_jid}...")
        cmd = ["wacli", "send", "file", "--to", sender_jid, "--file", gif_file, "--caption", "Here is your generated art!"]
        subprocess.run(cmd)
    
    save_last_run()
    print("Done!")
