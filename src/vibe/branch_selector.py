from __future__ import annotations

import subprocess
from typing import Optional

from .openai_client import generate_branch_name
from .output import error_exit


def select_branch_name(prompt: str, skip_ai: bool = False) -> str:
    """
    Prompt user to select or customize a branch name.
    First generates an AI suggestion, then lets user accept or provide their own.
    """
    if skip_ai:
        ai_suggestion = None
    else:
        try:
            ai_suggestion = generate_branch_name(prompt)
        except Exception:
            # If AI generation fails, continue without suggestion
            ai_suggestion = None
    
    # Use fzf with --print-query to allow custom input
    options = []
    if ai_suggestion:
        options.append(f"{ai_suggestion} (AI suggestion)")
    
    options.extend([
        "feature/",
        "fix/",
        "refactor/",
        "docs/",
        "test/",
    ])
    
    try:
        cmd = ["fzf", "--prompt", "Branch name: ", "--print-query", "--height", "40%"]
        
        result = subprocess.run(
            cmd,
            input="\n".join(options),
            text=True,
            capture_output=True,
        )
        
        # fzf with --print-query returns:
        # - First line: user's query (what they typed)
        # - Second line: selected option (if any)
        output_lines = result.stdout.strip().split("\n")
        
        if result.returncode == 0:
            # User selected something or pressed enter
            if len(output_lines) >= 2 and output_lines[1]:
                # User selected an option
                selected = output_lines[1]
                # Extract branch name (remove AI suggestion suffix if present)
                branch_name = selected.split(" (AI suggestion)")[0]
            else:
                # User just typed and pressed enter
                branch_name = output_lines[0] if output_lines else ""
        elif result.returncode == 1:
            # User cancelled (Ctrl-C or ESC)
            return ""
        else:
            # User typed something and pressed enter without selecting
            branch_name = output_lines[0] if output_lines else ""
        
        # Clean up the branch name
        branch_name = branch_name.strip()
        
        # If it's a prefix like "feature/", prompt again for the actual name
        if branch_name.endswith("/"):
            custom_name = input(f"{branch_name}")
            if custom_name:
                branch_name = f"{branch_name}{custom_name}"
            else:
                branch_name = ""
        
        return branch_name
        
    except FileNotFoundError:
        error_exit("Error: fzf not found. Please install fzf.")
        return ""
