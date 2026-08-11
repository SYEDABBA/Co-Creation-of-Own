#!/usr/bin/env python3
"""
YUGRAAL Co-Creator Engine - co_creator.py (Powered by Google Gemini API)
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
You are YUGRAAL Co-Creator Engine — an autonomous advanced developer that invents practical, robust, fully functional Python CLI tools.
You MUST reply ONLY with valid JSON. NO markdown formatting surrounding the JSON block.

Schema:
{
  "project_name": "UniqueDescriptiveCamelCaseName",
  "purpose": "Detailed multi-sentence explanation of what this tool does.",
  "usefulness": "Real-world developer or user utility benefits.",
  "how_to_use": "Terminal execution commands and complete usage examples.",
  "code": "COMPLETE runnable Python code without placeholders, ellipsis (...), or incomplete logic."
}

Rules:
1. 'code' MUST be at least 15 lines of functional Python code with full logic, error handling, and argument parsing.
2. 'project_name' MUST reflect the actual functionality (e.g., FileEncryptor, LogParser, SpeedTester), NOT generic names like YugraalTool.
3. ABSOLUTELY NO placeholders like '...' or 'TODO' or generic filler.
"""

USER_PROMPT_TEMPLATE = """
Invent a unique, practical Python utility script (e.g., system monitoring tool, file duplicate cleaner, API status checker, text summarizer, or developer helper).
Ensure it has complete, fully functional Python code.
"""

def get_available_models() -> List[str]:
    """
    Filter and return ONLY valid Gemini text-generation models.
    """
    models = []
    # Primary reliable text models
    preferred = ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-2.0-flash"]
    
    try:
        for m in genai.list_models():
            # Exclude audio/tts/embedding/gemma models
            name = m.name.lower()
            if "generateContent" in m.supported_generation_methods:
                if "gemini" in name and not any(x in name for x in ["tts", "embed", "imagen", "aqa", "vision"]):
                    models.append(m.name)
    except Exception as err:
        print(f"⚠️ Failed to list models: {err}")

    # Fallback to preferred models if filtering list is empty
    if not models:
        models = preferred
    else:
        # Put primary preferred models first if present
        models = sorted(models, key=lambda x: 0 if any(p in x for p in preferred) else 1)
        
    print(f"📋 Filtered text generation models: {models}")
    return models

def call_gemini(prompt_text: str) -> str:
    candidate_models = get_available_models()
    last_exception = None
    full_prompt = f"{SYSTEM_INSTRUCTION}\n\nTask:\n{prompt_text}"

    for model_name in candidate_models:
        try:
            print(f"🔄 Requesting from active text model: {model_name}...")
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
    cleaned = re.sub(r"```(?:json|python)?\n?", "", text, flags=re.IGNORECASE)
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

def clean_code_field(code_text: str) -> str:
    if not code_text:
        return ""
    fence_re = re.compile(r"```(?:\w+)?\n(.*)```", re.DOTALL)
    m = fence_re.search(code_text)
    code = m.group(1) if m else code_text
    return code.strip("\n\r ")

def sanitize_project_name(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", name)
    if not cleaned:
        return ""
    if not cleaned[0].isalpha():
        cleaned = "Yugraal" + cleaned
    return cleaned

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def write_file(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def validate_code_quality(source: str) -> Optional[str]:
    try:
        compile(source, "<generated_script>", "exec")
    except Exception as err:
        return f"Syntax Error: {err}"
    
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if len(lines) < 8:
        return "Generated code is too short or incomplete."
    if source.strip() in ["...", "pass"]:
        return "Code contains empty placeholder."
        
    return None

def format_readme(title: str, purpose: str, usefulness: str, how_to_use: str) -> str:
    return textwrap.dedent(f"""\
    # {title}

    ## Purpose
    {purpose}

    ## Usefulness
    {usefulness}

    ## How to Use
    {how_to_use}
    """)

def main():
    print("🔥 YUGRAAL Co-Creator Engine Starting (Gemini Powered)...")
    current_prompt = USER_PROMPT_TEMPLATE

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[{attempt}/{MAX_RETRIES}] Starting generation attempt...")
            raw_response = call_gemini(current_prompt)
            json_str = find_balanced_json(raw_response)
            if not json_str:
                raise ValueError("Could not extract a valid JSON object.")

            parsed = json.loads(json_str)
            required_keys = {"project_name", "purpose", "usefulness", "how_to_use", "code"}
            if not required_keys.issubset(parsed.keys()):
                raise ValueError("Missing required keys in JSON.")

            parsed["code"] = clean_code_field(parsed["code"])
            
            code_error = validate_code_quality(parsed["code"])
            if code_error:
                print(f"⚠️ Code Quality Warning: {code_error}")
                if attempt < MAX_RETRIES:
                    current_prompt = (
                        f"The code was rejected because: {code_error}. "
                        "Please provide a complete, working Python script with at least 15 lines of real logic."
                    )
                    time.sleep(TIMEOUT_BETWEEN_RETRIES)
                    continue
                else:
                    raise RuntimeError(f"Code validation failed: {code_error}")

            parsed["project_name"] = sanitize_project_name(parsed.get("project_name", "YugraalTool"))

            utc_now = datetime.datetime.now(datetime.timezone.utc)
            timestamp = utc_now.strftime("%Y%m%d_%H%M%S")
            folder_name = f"{parsed['project_name']}_{timestamp}"
            target_dir = os.path.join("My_Work", folder_name)
            ensure_dir(target_dir)

            write_file(os.path.join(target_dir, "main.py"), parsed["code"])
            write_file(os.path.join(target_dir, "README.md"), format_readme(
                parsed["project_name"], parsed["purpose"], parsed["usefulness"], parsed["how_to_use"]
            ))

            commit_msg = f"YUGRAAL Co-Creator: Added {parsed['project_name']} ({utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')})"
            write_file(os.path.join("My_Work", "last_commit_message.txt"), commit_msg)

            print(f"✅ SUCCESS: Created project '{parsed['project_name']}' in '{target_dir}'")
            sys.exit(0)

        except Exception as exc:
            print(f"❌ Attempt {attempt} failed: {exc}", file=sys.stderr)
            if attempt >= MAX_RETRIES:
                sys.exit(1)
            time.sleep(TIMEOUT_BETWEEN_RETRIES)

if __name__ == "__main__":
    main()
