#!/usr/bin/env python3
"""
YUGRAAL Co-Creator Engine - co_creator.py

Creates a new useful Python tool each run by calling the OpenAI API (gpt-4o-mini / gpt-4o).
Saves the generated code and README into My_Work/{project_name}_{YYYYMMDD_HHMMSS}/
Writes a commit message file to My_Work/last_commit_message.txt for the workflow to use.

Requires:
  - Environment variable OPENAI_API_KEY set.
  - pip install openai

Behavior:
  - Requests strictly-formatted JSON from the LLM.
  - Cleans and robustly parses the JSON.
  - Validates the Python code (compile check), asks the LLM to fix code if needed (retry loop).
  - Produces main.py and README.md. Prints concise status messages.
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
    import openai
except Exception as e:
    print("Missing dependency 'openai'. Install with: pip install openai", file=sys.stderr)
    raise

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(2)

openai.api_key = OPENAI_API_KEY

MODEL_NAME = "gpt-4o-mini"  # change to "gpt-4o" if available/preferred
MAX_RETRIES = 3
TIMEOUT_BETWEEN_RETRIES = 1  # seconds


SYSTEM_INSTRUCTION = """
You are YUGRAAL Co-Creator Engine — an autonomous inventor that MUST reply ONLY with JSON (no extra text).
Produce a JSON object matching EXACTLY this schema:

{
  "project_name": "UniqueCamelCaseName",
  "purpose": "Detailed purpose statement",
  "usefulness": "Detailed real-world use case",
  "how_to_use": "Step-by-step terminal execution instructions",
  "code": "Fully functional, error-free Python code"
}

Requirements:
- project_name must be a short CamelCase identifier (letters and numbers only, no spaces).
- code must be a complete Python program usable as a script (no "```" fences). If you include fences, they will be removed.
- How to use should show terminal commands and examples.
- Respond ONLY with the JSON object, nothing else.
"""

USER_PROMPT_TEMPLATE = """
Invent a small but genuinely useful Python utility/tool (single-file) that can be implemented as a command-line script.
Return JSON exactly as described by the system instructions. Ensure the Python code is complete and runnable.
Make the tool original and practical.

Return only the JSON object.
"""


def call_openai(messages, max_tokens=3000):
    """
    Call OpenAI ChatCompletion endpoint and return the text result.
    """
    try:
        resp = openai.ChatCompletion.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message["content"]
    except Exception as e:
        raise


def find_balanced_json(text: str) -> Optional[str]:
    """
    Try to extract the first balanced JSON object substring from text.
    Returns string including the enclosing braces, or None.
    """
    # Remove common markdown code fences first to avoid hiding braces
    cleaned = re.sub(r"```(?:json|python)?\n?", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned)

    # Find first '{' and attempt to find matching '}' by counting braces
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
    Remove triple backticks and any leading language hints, then trim.
    """
    if not code_text:
        return code_text
    # Remove triple backtick fences if present
    # Keep inner content only.
    # Example fences: ```python\n...``` or ```\n...\n```
    fence_re = re.compile(r"```(?:\w+)?\n(.*)```", re.DOTALL)
    m = fence_re.search(code_text)
    if m:
        code = m.group(1)
    else:
        code = code_text
    # Strip leading/trailing whitespace
    code = code.strip("\n\r ")
    # If code was returned as a JSON string with escaped newlines, unescape:
    code = code.encode('utf-8').decode('unicode_escape') if "\\n" in code else code
    return code


def sanitize_project_name(name: str) -> str:
    """
    Keep only alphanumeric characters, enforce CamelCase-like capitalization if possible.
    Fallback to Project+timestamp if sanitization empties the name.
    """
    if not name:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", name)
    if not cleaned:
        return ""
    # Ensure first char is letter
    if not cleaned[0].isalpha():
        cleaned = "P" + cleaned
    return cleaned


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def write_file(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def compile_python_source(source: str) -> Optional[str]:
    """
    Attempt to compile the source. Return None on success, or the error message.
    """
    try:
        compile(source, "<generated_main>", "exec")
        return None
    except Exception as e:
        return str(e)


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


def create_prompt_messages_for_initial_call():
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": USER_PROMPT_TEMPLATE},
    ]


def create_followup_fix_prompt(prev_json: dict, error_text: str) -> list:
    """
    Ask the model to return the full JSON again but with corrected code to fix the provided syntax/runtime error.
    """
    msg = (
        "The previously returned JSON's 'code' field has a Python error when compiled/executed. "
        "Provide a corrected JSON object (same schema) where only the 'code' content is changed to fix the error.\n\n"
        f"Error encountered:\n{error_text}\n\n"
        "Return the full JSON object and nothing else."
    )
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": msg},
        {"role": "assistant", "content": json.dumps(prev_json)},  # include previous as context
    ]


def main():
    print("YUGRAAL Co-Creator starting...")
    messages = create_prompt_messages_for_initial_call()

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[{attempt}] Requesting invention from LLM...")
            raw = call_openai(messages)
            if not raw or not raw.strip():
                raise RuntimeError("Empty response from LLM")

            # Try to find JSON substring
            json_sub = find_balanced_json(raw)
            if not json_sub:
                # Maybe the model returned code-fenced JSON; remove fences and try again
                stripped = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
                stripped = re.sub(r"```\s*", "", stripped)
                json_sub = find_balanced_json(stripped)
            if not json_sub:
                raise ValueError("Could not locate a balanced JSON object in model response.")

            try:
                parsed = json.loads(json_sub)
            except json.JSONDecodeError as je:
                # Try some cleanup: replace smart quotes, trailing commas, single quotes -> double quotes if safe
                candidate = json_sub
                candidate = candidate.replace('\u201c', '"').replace('\u201d', '"').replace("“", '"').replace("”", '"')
                candidate = re.sub(r",\s*}", "}", candidate)
                candidate = re.sub(r",\s*]", "]", candidate)
                # Attempt to coerce single-quotes to double quotes only when keys/values are enclosed with single quotes
                candidate2 = re.sub(r"(?P<pre>[:\s,\[]?)'(?P<inner>[^']*?)'(?P<post>[\s,\]\}])", r'\1"\2"\3', candidate)
                try:
                    parsed = json.loads(candidate2)
                except Exception:
                    raise RuntimeError(f"JSON decode failed: {je}. Raw JSON candidate: {json_sub[:400]}")

            # Check required keys
            required_keys = {"project_name", "purpose", "usefulness", "how_to_use", "code"}
            if not required_keys.issubset(parsed.keys()):
                missing = required_keys - set(parsed.keys())
                raise ValueError(f"Missing required keys in JSON: {missing}")

            # Clean code field
            parsed["code"] = clean_code_field(parsed["code"])

            # Sanitize project name
            original_name = parsed.get("project_name", "") or ""
            sanitized_name = sanitize_project_name(original_name)
            if not sanitized_name:
                sanitized_name = "Project" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            parsed["project_name"] = sanitized_name

            # Validate Python code compiles
            compile_error = compile_python_source(parsed["code"])
            if compile_error:
                last_error = compile_error
                print(f"Compilation error detected: {compile_error}")
                if attempt < MAX_RETRIES:
                    # Ask LLM to fix code only
                    messages = create_followup_fix_prompt(parsed, compile_error)
                    print("Requesting code fix from LLM...")
                    time.sleep(TIMEOUT_BETWEEN_RETRIES)
                    continue
                else:
                    raise RuntimeError(f"Compilation failed after {MAX_RETRIES} attempts: {compile_error}")

            # All good: write files
            now = datetime.datetime.utcnow()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            folder_name = f"{parsed['project_name']}_{timestamp}"
            target_dir = os.path.join("My_Work", folder_name)
            ensure_dir(target_dir)

            main_py_path = os.path.join(target_dir, "main.py")
            readme_path = os.path.join(target_dir, "README.md")
            write_file(main_py_path, parsed["code"])
            readme_content = format_readme(parsed["project_name"], parsed["purpose"], parsed["usefulness"], parsed["how_to_use"])
            write_file(readme_path, readme_content)

            # Write a commit message file for the workflow to consume
            commit_message = f"YUGRAAL Co-Creator: Add {parsed['project_name']} ({now.strftime('%Y-%m-%d %H:%M:%S UTC')})"
            commit_msg_file = os.path.join("My_Work", "last_commit_message.txt")
            ensure_dir(os.path.dirname(commit_msg_file) or ".")
            write_file(commit_msg_file, commit_message)

            print(f"SUCCESS: Created project '{parsed['project_name']}' in {target_dir}")
            print(f"Files written: {main_py_path}, {readme_path}")
            print(f"Commit message written to: {commit_msg_file}")
            sys.exit(0)

        except Exception as exc:
            print(f"Attempt {attempt} failed: {exc}", file=sys.stderr)
            if attempt >= MAX_RETRIES:
                print("Max attempts reached. Exiting with failure.", file=sys.stderr)
                # Write a failure marker file for diagnostics
                try:
                    ensure_dir("My_Work")
                    write_file(os.path.join("My_Work", "last_error.txt"), f"Last error:\n{exc}\n")
                except Exception:
                    pass
                sys.exit(1)
            else:
                time.sleep(TIMEOUT_BETWEEN_RETRIES)
                continue


if __name__ == "__main__":
    main()
