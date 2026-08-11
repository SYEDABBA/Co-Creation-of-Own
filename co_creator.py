#!/usr/bin/env python3
"""
YUGRAAL Co-Creator Web Engine - co_creator.py
Autonomous System generating Production-Ready Single Page Web Applications.
"""

import os
import sys
import json
import re
import time
import textwrap
import datetime
from typing import Optional, List

try:
    import google.generativeai as genai
except ImportError:
    print("Missing dependency 'google-generativeai'. Install with: pip install google-generativeai", file=sys.stderr)
    sys.exit(1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(2)

genai.configure(api_key=GEMINI_API_KEY)

MAX_RETRIES = 3
TIMEOUT_BETWEEN_RETRIES = 2

SYSTEM_INSTRUCTION = """
You are YUGRAAL Co-Creator Web Engine — an elite AI software architect that invents futuristic, highly functional, beautifully designed web applications.
You MUST reply ONLY with valid JSON (no surrounding markdown wrappers outside JSON).

Output Schema:
{
  "project_name": "UniqueDescriptiveCamelCaseName",
  "purpose": "Detailed explanation of what this web app does.",
  "usefulness": "Why users will love and use this tool daily.",
  "live_url_path": "Path to access the live app",
  "html_code": "COMPLETE standalone index.html containing modern HTML5, embedded CSS (or Tailwind CSS CDN), and embedded modular JavaScript logic."
}

Rules:
1. 'html_code' MUST be a fully functional, beautiful single-file web application containing <!DOCTYPE html>, head with Tailwind CDN (<script src='https://cdn.tailwindcss.com'></script>), Lucide/FontAwesome icons CDN, clean dark-mode futuristic glassmorphism UI, and functional JS logic.
2. The web app MUST be an impressive utility (e.g., Cyberpunk Audio Visualizer, Live Developer Code Playground, AI Prompt Builder & Manager, Realtime Crypto/Stock Dashboard Visualizer, Interactive Canvas Game/Physics Engine, Advanced Markdown/PDF Studio).
3. ABSOLUTELY NO empty logic, placeholders, or incomplete features. Everything rendered on screen must work smoothly.
4. Do NOT use markdown code fences inside JSON string fields.
"""

USER_PROMPT_TEMPLATE = """
Invent a high-end, responsive, visually stunning web application. 
Use modern dark UI, smooth animations, interactive features, and Tailwind CSS.
Provide 100% working code inside 'html_code'.
"""

def get_available_models() -> List[str]:
    models = []
    preferred = ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-2.0-flash"]
    try:
        for m in genai.list_models():
            name = m.name.lower()
            if "generateContent" in m.supported_generation_methods:
                if "gemini" in name and not any(x in name for x in ["tts", "embed", "imagen", "aqa", "vision"]):
                    models.append(m.name)
    except Exception as err:
        print(f"⚠️ Failed to list models: {err}")

    if not models:
        models = preferred
    else:
        models = sorted(models, key=lambda x: 0 if any(p in x for p in preferred) else 1)
        
    return models

def call_gemini(prompt_text: str) -> str:
    candidate_models = get_available_models()
    last_exception = None
    full_prompt = f"{SYSTEM_INSTRUCTION}\n\nTask:\n{prompt_text}"

    for model_name in candidate_models:
        try:
            print(f"🔄 Requesting from active model: {model_name}...")
            model = genai.GenerativeModel(model_name=model_name)
            response = model.generate_content(full_prompt)
            if response and response.text:
                print(f"✨ Success using model: {model_name}")
                return response.text
        except Exception as exc:
            print(f"⚠️ Model {model_name} failed: {exc}")
            last_exception = exc
            continue

    raise RuntimeError(f"All available Gemini models failed. Last error: {last_exception}")

def find_balanced_json(text: str) -> Optional[str]:
    cleaned = re.sub(r"```(?:json|html)?\n?", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned)

    start_idx = cleaned.find("{")
    if start_idx == -1:
        return None
    
    depth = 0
    for i in range(start_idx, len(cleaned)):
        ch = cleaned[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start_idx:i + 1]
    return None

def clean_html_field(html_text: str) -> str:
    if not html_text:
        return ""
    fence_re = re.compile(r"```(?:\w+)?\n(.*)```", re.DOTALL)
    m = fence_re.search(html_text)
    code = m.group(1) if m else html_text
    return code.strip("\n\r ")

def sanitize_project_name(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", name)
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "YugraalWebApp" + cleaned
    return cleaned

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def write_file(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def validate_html_quality(source: str) -> Optional[str]:
    if "<html" not in source.lower() or "</html>" not in source.lower():
        return "Invalid HTML structure: missing <html> tags."
    if len(source.splitlines()) < 25:
        return "Web app code is too basic or incomplete."
    return None

def format_readme(title: str, purpose: str, usefulness: str, app_folder: str) -> str:
    return textwrap.dedent(f"""\
    # 🚀 {title} (YUGRAAL Invention)

    ## 🎯 Purpose
    {purpose}

    ## 🔥 Usefulness
    {usefulness}

    ## 🌐 Live Access
    Open `index.html` directly in your browser or access it via GitHub Pages:
    `https://SYEDABBA.github.io/Co-Creation-of-Own/My_Work/{app_folder}/index.html`
    """)

def main():
    print("🔥 YUGRAAL Web App Engine Starting...")
    current_prompt = USER_PROMPT_TEMPLATE

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[{attempt}/{MAX_RETRIES}] Generating Web App attempt...")
            raw_response = call_gemini(current_prompt)
            json_str = find_balanced_json(raw_response)
            if not json_str:
                raise ValueError("Could not extract a valid JSON object.")

            parsed = json.loads(json_str)
            required_keys = {"project_name", "purpose", "usefulness", "html_code"}
            if not required_keys.issubset(parsed.keys()):
                raise ValueError("Missing required keys in JSON.")

            parsed["html_code"] = clean_html_field(parsed["html_code"])
            
            html_error = validate_html_quality(parsed["html_code"])
            if html_error:
                print(f"⚠️ HTML Validation Warning: {html_error}")
                if attempt < MAX_RETRIES:
                    current_prompt = (
                        f"The generated web app was rejected: {html_error}. "
                        "Please provide a complete, stunning single-file HTML5 app with Tailwind CSS and interactive JS."
                    )
                    time.sleep(TIMEOUT_BETWEEN_RETRIES)
                    continue
                else:
                    raise RuntimeError(f"HTML validation failed: {html_error}")

            parsed["project_name"] = sanitize_project_name(parsed.get("project_name", "YugraalWebApp"))

            utc_now = datetime.datetime.now(datetime.timezone.utc)
            timestamp = utc_now.strftime("%Y%m%d_%H%M%S")
            folder_name = f"{parsed['project_name']}_{timestamp}"
            target_dir = os.path.join("My_Work", folder_name)
            ensure_dir(target_dir)

            write_file(os.path.join(target_dir, "index.html"), parsed["html_code"])
            write_file(os.path.join(target_dir, "README.md"), format_readme(
                parsed["project_name"], parsed["purpose"], parsed["usefulness"], folder_name
            ))

            commit_msg = f"YUGRAAL Co-Creator: Launched Web App {parsed['project_name']} ({utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')})"
            write_file(os.path.join("My_Work", "last_commit_message.txt"), commit_msg)

            print(f"✅ SUCCESS: Created Web App '{parsed['project_name']}' in '{target_dir}'")
            sys.exit(0)

        except Exception as exc:
            print(f"❌ Attempt {attempt} failed: {exc}", file=sys.stderr)
            if attempt >= MAX_RETRIES:
                sys.exit(1)
            time.sleep(TIMEOUT_BETWEEN_RETRIES)

if __name__ == "__main__":
    main()

