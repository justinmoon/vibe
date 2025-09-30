from __future__ import annotations

import json
import os
import subprocess
import textwrap
import urllib.error
import urllib.request

from .output import error_exit, warning


def fetch_openai_key() -> str | None:
    env_key = os.environ.get("VIBE_OPENAI_KEY")
    if env_key:
        return env_key
    try:
        result = subprocess.run(["op", "read", "op://cli/openai/configs"], capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    api_key = result.stdout.strip()
    return api_key or None


def openai_chat(api_key: str, system_prompt: str, user_content: str, *, max_tokens: int) -> str:
    base = os.environ.get("VIBE_OPENAI_API_BASE", "https://api.openai.com")
    url = f"{base.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_exit("Error: OpenAI request failed with status %s", exc.code)
    except urllib.error.URLError as exc:
        error_exit("Error: OpenAI request failed (%s)", exc.reason)

    try:
        parsed = json.loads(body)
        return parsed["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, json.JSONDecodeError):
        error_exit("Error: Unexpected response from OpenAI")


def sanitize_branch_name(name: str) -> str:
    lowered = name.strip().lower()
    lowered = lowered.lstrip("-_ ")
    cleaned = []
    previous_dash = False
    for char in lowered:
        if char.isalnum():
            cleaned.append(char)
            previous_dash = False
        else:
            if not previous_dash:
                cleaned.append("-")
            previous_dash = True
    sanitized = "".join(cleaned).strip("-")
    return sanitized


def generate_branch_name(prompt: str) -> str:
    api_key = fetch_openai_key()
    if not api_key:
        warning("Error: AI branch name generation failed")
        warning("OpenAI API key not found in 1Password (op://cli/openai/configs)")
        warning("Fix the issue or use --no-worktree to work in current directory")
        raise SystemExit(1)

    essence = openai_chat(
        api_key,
        "Extract the main topic and intent from this development request in 5-10 words. Focus on the key feature, component, or goal being worked on.",
        prompt,
        max_tokens=30,
    )
    branch = openai_chat(
        api_key,
        textwrap.dedent(
            """\
            Generate a concise git branch name (2-4 words, hyphenated, lowercase). Focus on the main feature/component. Examples:
            - "implement multi-user chats" → group-chats
            - "event-driven architecture refactor" → event-architecture
            - "fix authentication bug" → fix-auth
            - "add dark mode toggle" → dark-mode
            - "database migration system" → db-migration
            - "api rate limiting" → rate-limiting
            Return only the branch name, no quotes or explanations.
            """
        ).strip(),
        essence,
        max_tokens=10,
    )
    sanitized = sanitize_branch_name(branch)
    if not sanitized:
        error_exit("Error: Generated invalid branch name")
    return sanitized
