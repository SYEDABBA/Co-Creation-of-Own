#!/usr/bin/env python3
"""
YUGRAAL Co-Creator Engine - co_creator.py (Powered by Google Gemini API)

Autonomous AI system that invents a new Python utility script on every run,
validates syntax, handles self-repair on failure, and outputs structured code & docs.
"""

import os
import sys
import json
import re
import time
import textwrap
import datetime
from typing import Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Missing dependency 'google-genai'. Install with: pip install google-genai", file=sys.stderr)
    sys.exit(1)

# Check API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(2)

# Initialize modern Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-2.5-flash"  # Fast, highly accurate, and free-tier friendly
MAX_RETRIES = 3
TIMEOUT_BETWEEN_RETRIES = 2  # seconds

SYSTEM_INSTRUCTION = """
You are YUGRAAL Co-Creator Engine — an autonomous inventor that MUST reply ONLY with valid JSON (no markdown wrapping, no text outside JSON).
Produce a JSON object matching EXACTLY this schema:

{
  "project_name": "UniqueCamelCaseName",
  "purpose": "Detailed purpose statement",
  "usefulness": "Detailed real-world use case",
  "how_to_use": "Step-by-step terminal execution instructions",
  "code": "Fully functional, error-free Python code"
}

Requirements:
- project_name must be a short CamelCase identifier (letters and numbers only).
- code must be a complete, self-contained, runnable Python script. Do NOT include markdown code fences (like ```python) in the JSON value.
- how_to_use should show exact terminal commands and usage examples.
- Respond strictly with valid JSON object.
"""

USER_PROMPT_TEMPLATE = """
Invent a small but genuinely useful Python CLI utility that solves a practical developer or daily automation task.
Return JSON strictly matching the system instruction schema.
Make the tool practical, original, and clean.
"""


def call_gemini(prompt_text: str) -> str:
    """
    Call Google Gemini API using the latest google-genai SDK.
    """
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                response_mime_type="application/json",
            )
        )
        return response.text or ""
    except Exception as exc:
        raise RuntimeError(f"Gemini API Call failed: {exc}") from exc


def find_balanced_json(text: str) -> Optional[str]:
    """
    Extract the first balanced JSON object substring from raw response text.
    """
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
    """
    Strip backticks and format code safely.
    """
    if not code_text:
        return ""
    
    fence_re = re.compile(r"```(?:\w+)?\n(.*)```", re.DOTALL)
    m = fence_re.search(code_text)
    code = m.group(1) if m else code_text

    code = code.strip("\n\r ")
    if "\\n" in code and "\n" not in code:
        try:
            code = code.encode('utf-8').decode('unicode_escape')
        except Exception:
            pass
    return code


def sanitize_project_name(name: str) -> str:
    """
    Sanitize project name to valid CamelCase directory format.
    """
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


def compile_python_source(source: str) -> Optional[str]:
    """
    Validates Python syntax. Returns error string if invalid, else None.
    """
    try:
        compile(source, "<generated_script>", "exec")
        return None
    except Exception as err:
        return str(err)


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
            print(f"[{attempt}/{MAX_RETRIES}] Requesting invention from YUGRAAL Engine...")
            raw_response = call_gemini(current_prompt)
            if not raw_response.strip():
                raise RuntimeError("Empty response received from Gemini.")

            json_str = find_balanced_json(raw_response)
            if not json_str:
                raise ValueError("Could not extract a valid JSON object from Gemini response.")

            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                cleaned_json = json_str.replace("“", '"').replace("”", '"')
                cleaned_json = re.sub(r",\s*}", "}", cleaned_json)
                cleaned_json = re.sub(r",\s*]", "]", cleaned_json)
                parsed = json.loads(cleaned_json)

            required_keys = {"project_name", "purpose", "usefulness", "how_to_use", "code"}
            if not required_keys.issubset(parsed.keys()):
                missing = required_keys - set(parsed.keys())
                raise ValueError(f"JSON missing required keys: {missing}")

            parsed["code"] = clean_code_field(parsed["code"])
            sanitized_name = sanitize_project_name(parsed.get("project_name", ""))
            if not sanitized_name:
                sanitized_name = "YugraalTool" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
            parsed["project_name"] = sanitized_name

            # Test compile code syntax
            compile_err = compile_python_source(parsed["code"])
            if compile_err:
                print(f"⚠️ Syntax Error detected: {compile_err}")
                if attempt < MAX_RETRIES:
                    print("🔄 Triggering Self-Healing repair loop...")
                    current_prompt = (
                        f"The generated code in 'code' had a syntax error:\n{compile_err}\n\n"
                        f"Previous output:\n{json.dumps(parsed)}\n\n"
                        "Please fix the error and return the full corrected JSON strictly."
                    )
                    time.sleep(TIMEOUT_BETWEEN_RETRIES)
                    continue
                else:
                    raise RuntimeError(f"Code compilation failed after max retries: {compile_err}")

            # Directories setup & saving
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            timestamp = utc_now.strftime("%Y%m%d_%H%M%S")
            folder_name = f"{parsed['project_name']}_{timestamp}"
            target_dir = os.path.join("My_Work", folder_name)
            ensure_dir(target_dir)

            main_py_path = os.path.join(target_dir, "main.py")
            readme_path = os.path.join(target_dir, "README.md")

            write_file(main_py_path, parsed["code"])
            readme_body = format_readme(
                parsed["project_name"],
                parsed["purpose"],
                parsed["usefulness"],
                parsed["how_to_use"]
            )
            write_file(readme_path, readme_body)

            # Generate commit message file
            commit_msg = f"YUGRAAL Co-Creator: Added {parsed['project_name']} ({utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')})"
            commit_msg_path = os.path.join("My_Work", "last_commit_message.txt")
            ensure_dir(os.path.dirname(commit_msg_path))
            write_file(commit_msg_path, commit_msg)

            print(f"✅ SUCCESS: Created project '{parsed['project_name']}' in '{target_dir}'")
            print(f"📄 Files generated: {main_py_path}, {readme_path}")
            sys.exit(0)

        except Exception as exc:
            print(f"❌ Attempt {attempt} failed: {exc}", file=sys.stderr)
            if attempt >= MAX_RETRIES:
                print("💥 Max attempts reached. Exiting script.", file=sys.stderr)
                ensure_dir("My_Work")
                write_file(os.path.join("My_Work", "last_error.txt"), str(exc))
                sys.exit(1)
            time.sleep(TIMEOUT_BETWEEN_RETRIES)


if __name__ == "__main__":
    main()
