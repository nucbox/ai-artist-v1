import os
import subprocess
import json
import datetime
import asyncio
import sys
from playwright.async_api import async_playwright
import imageio.v3 as iio
from google import genai

# Setup unbuffered output for logging
sys.stdout.reconfigure(line_buffering=True)

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
gallery_dir = os.path.join(script_dir, 'gallery')
queue_dir = os.path.join(script_dir, 'queue')
state_file = os.path.join(script_dir, 'last_run.txt')
os.makedirs(gallery_dir, exist_ok=True)
os.makedirs(queue_dir, exist_ok=True)

# The design patterns to enforce
PATTERNS = """
Use complex easing functions like easeInOutQuint, restrict color palettes to 4-5 vivid hex codes,
utilize object-oriented classes with asynchronous animation states, avoid pure randomness in favor
of noise or grid-anchored offsets. Make it look like a professional p5.js generative art piece.
IMPORTANT PERFORMANCE CONSTRAINTS: 
1. If generating a 3D sketch, limit the number of active objects to a maximum of 3 to avoid rendering timeouts.
2. Ensure you position the camera properly so all objects are visible (e.g., 'camera(0, 0, 1500, 0, 0, 0, 0, 1, 0)').
3. Keep the scene geometry lightweight (avoid extreme recursive fractal depth).
4. COMPLEXITY: If a user asks for 'chaotic storms', 'swarms', or 'data shards', generate at least 50-100 instances of the particles/shards and animate them using Perlin noise, NOT just a single cube. A single cube is NEVER an acceptable result for complex prompts.
"""

gemini_client = genai.Client()
api_key_debug = os.environ.get('GEMINI_API_KEY', 'NONE')
masked_key = (api_key_debug[:5] + "..." + api_key_debug[-4:]) if len(api_key_debug) > 9 else "SHORT/MISSING"
print(f"DEBUG: Using API key: {masked_key}", flush=True)

def get_last_run():
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            return f.read().strip()
    return "2000-01-01T00:00:00Z"

def save_last_run():
    with open(state_file, 'w') as f:
        f.write(datetime.datetime.utcnow().isoformat() + "Z")

def ask_gemini(prompt):
    print("DEBUG: Sending request to Gemini...", flush=True)
    response = gemini_client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt
    )
    print("DEBUG: Received response from Gemini.", flush=True)
    return response.text.strip()

def get_muse_prompt():
    if "MUSE_TEXT" in os.environ:
        user_text = os.environ["MUSE_TEXT"]
        sender_jid = os.environ.get("SENDER_JID", "")
        print(f"Received user message from listener: {user_text}", flush=True)
        try:
            expanded = ask_gemini(f"Act as an avant-garde digital art director. Take this raw idea: '{user_text}' and expand it into a rich generative art prompt. Return ONLY the prompt text.")
            if expanded:
                return expanded, sender_jid
        except Exception as e:
            print(f"Gemini API error: {e}", flush=True)
        return user_text, sender_jid
    return "A complex geometric landscape of rippling cubes in neon green and deep purple.", None

def generate_code(prompt):
    print("Generating code from concept...", flush=True)
    sys_prompt = f"You are an expert generative artist writing p5.js code. The concept is: {prompt}. Apply these patterns strictly: {PATTERNS}. Return ONLY the raw HTML string containing the complete p5.js sketch. No markdown fences, no explanations."
    try:
        html = ask_gemini(sys_prompt)
        if html.startswith("```html"):
            html = html[7:]
        if html.endswith("```"):
            html = html[:-3]
        return html.strip()
    except Exception as e:
        print(f"Gemini API error: {e}", flush=True)
        return ""

async def render_gif(html_code):
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    code_filename = os.path.join(gallery_dir, f"ai_art_{timestamp}.html")
    with open(code_filename, "w") as f:
        f.write(html_code)
        
    html_path = os.path.join(script_dir, "dynamic_canvas.html")
    with open(html_path, "w") as f:
        f.write(html_code)
    
    print("Rendering with Playwright...", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--use-gl=swiftshader', '--disable-gpu'])
        page = await browser.new_page()
        page.on('console', lambda msg: print(f"BROWSER CONSOLE: {msg.text}", flush=True))
        page.on('pageerror', lambda err: print(f"BROWSER ERROR: {err}", flush=True))
        
        await page.goto("http://localhost:8000/dynamic_canvas.html")
        await page.wait_for_selector('canvas', timeout=20000)
        await asyncio.sleep(3)
        
        frames = []
        for i in range(60):
            path = os.path.join(script_dir, f"frame_{i:03d}.png")
            try:
                await page.screenshot(path=path, timeout=60000)
                frames.append(iio.imread(path))
                os.remove(path)
            except Exception as e:
                print(f"Error capturing frame {i}: {e}", flush=True)
            await asyncio.sleep(0.05)
            
        filename = os.path.join(gallery_dir, f"ai_art_{timestamp}.gif")
        iio.imwrite(filename, frames, duration=50, loop=0)
        print(f"Artwork saved: {filename}", flush=True)
        await browser.close()
        return filename

if __name__ == "__main__":
    concept, sender_jid = get_muse_prompt()
    html_code = generate_code(concept)
    if not html_code:
        print("Failed to generate code.", flush=True)
        exit(1)
        
    try:
        gif_file = asyncio.run(render_gif(html_code))
    except Exception as e:
        print(f"Art generation failed: {str(e)}", flush=True)
        exit(1)
    
    # Save the request to queue so listener can handle it
    delivery_request = {
        "gif_file": gif_file,
        "sender_jid": sender_jid,
        "caption": "Here is your generated art!"
    }
    with open(os.path.join(queue_dir, f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), "w") as f:
        json.dump(delivery_request, f)
    
    save_last_run()
    print("Done!", flush=True)
