import os
import subprocess
import json
import datetime
import asyncio
from playwright.async_api import async_playwright
import imageio.v3 as iio

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

def get_last_run():
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            return f.read().strip()
    return "2000-01-01T00:00:00Z"

def save_last_run():
    with open(state_file, 'w') as f:
        f.write(datetime.datetime.utcnow().isoformat() + "Z")

def get_muse_prompt():
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
                user_text = messages[0].get('text', '')
                if user_text:
                    print(f"Found user message: {user_text}")
                    # Enhance with Gemini
                    gem_cmd = ["gemini", f"Act as an avant-garde digital art director. Take this raw idea: '{user_text}' and expand it into a rich generative art prompt. Return ONLY the prompt text."]
                    prompt_res = subprocess.run(gem_cmd, capture_output=True, text=True)
                    if prompt_res.returncode == 0 and prompt_res.stdout.strip():
                        return prompt_res.stdout.strip()
    except Exception as e:
        print(f"Warning: WhatsApp fetch failed: {e}")
        
    # Autonomous mode
    print("No new messages found. Running autonomous brainstorming...")
    gem_cmd = ["gemini", "Act as an avant-garde digital art director. Generate a highly creative generative art concept based on nature, current digital trends, or mathematics. Return ONLY the text description of the concept."]
    prompt_res = subprocess.run(gem_cmd, capture_output=True, text=True)
    if prompt_res.returncode == 0:
        return prompt_res.stdout.strip()
    return "A complex geometric landscape of rippling cubes in neon green and deep purple."

def generate_code(prompt):
    print("Generating code from concept...")
    sys_prompt = f"You are an expert generative artist writing p5.js code. The concept is: {prompt}. Apply these patterns strictly: {PATTERNS}. Return ONLY the raw HTML string containing the complete p5.js sketch. No markdown fences, no explanations."
    gem_cmd = ["gemini", sys_prompt]
    res = subprocess.run(gem_cmd, capture_output=True, text=True)
    html = res.stdout.strip()
    if html.startswith("```html"):
        html = html[7:]
    if html.endswith("```"):
        html = html[:-3]
    return html.strip()

async def render_gif(html_code):
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
            
        filename = os.path.join(gallery_dir, f"ai_art_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.gif")
        iio.imwrite(filename, frames, duration=50, loop=0)
        print(f"Artwork saved: {filename}")
        await browser.close()
        return filename

if __name__ == "__main__":
    concept = get_muse_prompt()
    print(f"CONCEPT:\n{concept}\n")
    
    html_code = generate_code(concept)
    
    asyncio.run(render_gif(html_code))
    save_last_run()
    print("Done!")
