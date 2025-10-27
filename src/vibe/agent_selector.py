from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .model_selector import select_model, select_reasoning_effort
from .output import error_exit
from .usage_tracker import queue_increment, get_sorted_by_usage, get_usage_count


def get_available_agents() -> List[str]:
    """Get list of available agents from vibe-rules directory."""
    import os
    from pathlib import Path
    
    # Get the directory where this script is located
    current_dir = Path(__file__).parent
    agents_dir = current_dir.parent.parent / "vibe-rules" / "rules" / "agents"
    
    if not agents_dir.exists():
        # Fallback to known agents if directory doesn't exist
        return ["claude", "codex", "amp", "oc", "droid"]
    
    agents = []
    for agent_file in agents_dir.glob("*.md"):
        agents.append(agent_file.stem)
    
    # Add known agents that might not have .md files
    for agent in ["amp", "oc", "droid"]:
        if agent not in agents:
            agents.append(agent)
    
    return sorted(agents)





def run_fzf_selection(
    options: List[str], 
    prompt: str = "Select", 
    multi: bool = False, 
    category: str | None = None,
    track_usage: bool = True
) -> List[str]:
    """Run fzf to let user select from options.
    
    Args:
        options: List of options to display
        prompt: Prompt text for fzf
        multi: Allow multiple selections
        category: Category for usage tracking (e.g., "agents", "models")
        track_usage: Whether to track usage (default: True)
    """
    # Sort by usage if category is provided
    if category and track_usage:
        options = get_sorted_by_usage(options, category)
        
        # Add usage count to display
        display_options = []
        for option in options:
            count = get_usage_count(category, option)
            if count > 0:
                display_options.append(f"{option} (used {count} times)")
            else:
                display_options.append(option)
    else:
        display_options = options
    
    try:
        cmd = ["fzf", "--prompt", f"{prompt}: "]
        if multi:
            cmd.extend(["--multi"])
        
        result = subprocess.run(
            cmd,
            input="\n".join(display_options),
            text=True,
            capture_output=True,
        )
        
        if result.returncode == 0:
            selected = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            # Extract original option names (remove usage count if present)
            selected = [s.split(" (used")[0] for s in selected]
            # Queue usage tracking (will be committed after successful launch)
            if category and track_usage:
                for item in selected:
                    queue_increment(category, item)
            return selected
        else:
            return []
    except FileNotFoundError:
        error_exit("Error: fzf not found. Please install fzf to use agent selection.")
        return []


def select_single_agent() -> Optional[str]:
    """Prompt user to select a single agent."""
    agents = get_available_agents()
    if not agents:
        error_exit("No agents found")
        return None
    
    selected = run_fzf_selection(agents, "Select agent", category="agents")
    return selected[0] if selected else None


def select_agents_for_duo() -> Optional[Tuple[str, str, Optional[str], Optional[str]]]:
    """Prompt user to select two agents for duo mode (can be same agent)."""
    agents = get_available_agents()
    if not agents:
        error_exit("No agents found")
        return None
    
    # Select first agent
    selected = run_fzf_selection(agents, "Select first agent", multi=False, category="agents")
    if not selected:
        return None
    
    first_agent = selected[0]
    
    # Select model for first agent if needed
    first_model = None
    first_reasoning = None
    if first_agent in ["oc", "codex", "droid"]:
        first_model = select_model(first_agent)
        if not first_model:
            return None
        # Select reasoning effort for codex and droid (optional)
        if first_agent in ["codex", "droid"]:
            first_reasoning = select_reasoning_effort(first_model, first_agent)
            # Reasoning effort is optional - continue even if None
    
    # Select second agent (allow same agent)
    selected_second = run_fzf_selection(agents, "Select second agent", multi=False, category="agents")
    if not selected_second:
        return None
    
    second_agent = selected_second[0]
    
    # Select model for second agent if needed
    second_model = None
    second_reasoning = None
    if second_agent in ["oc", "codex", "droid"]:
        second_model = select_model(second_agent)
        if not second_model:
            return None
        # Select reasoning effort for codex and droid (optional)
        if second_agent in ["codex", "droid"]:
            second_reasoning = select_reasoning_effort(second_model, second_agent)
            # Reasoning effort is optional - continue even if None
    
    return (first_agent, second_agent, first_model, second_model, first_reasoning, second_reasoning)


def select_agent_mode() -> Optional[str]:
    """Prompt user to select agent mode (single, duo, review)."""
    modes = [
        "single",
        "duo",
        "review",
    ]
    
    selected = run_fzf_selection(modes, "Select mode", category="modes")
    
    if not selected:
        return None
    
    return selected[0]


def prompt_agent_selection() -> Optional[Tuple[str, Union[Tuple[str, Optional[str]], Tuple[str, str, Optional[str], Optional[str]]]]]:
    """
    Main function to prompt for agent selection.
    Returns: (mode, agents_info) where mode is 'single', 'duo', or 'review'
            and agents_info varies by mode:
            - single: (agent, model, reasoning)
            - duo/review: (agent1, agent2, model1, model2, reasoning1, reasoning2)
    """
    mode = select_agent_mode()
    if not mode:
        return None
    
    if mode in ["duo", "review"]:
        duo_selection = select_agents_for_duo()
        if not duo_selection:
            return None
        return mode, duo_selection
    else:
        # For single mode, select the primary agent
        agent = select_single_agent()
        if not agent:
            return None
        
        # If agent supports model selection, prompt for it
        selected_model = None
        selected_reasoning = None
        if agent in ["oc", "codex", "droid"]:
            selected_model = select_model(agent)
            if not selected_model:
                return None
            # Select reasoning effort for codex and droid (optional)
            if agent in ["codex", "droid"]:
                selected_reasoning = select_reasoning_effort(selected_model, agent)
                # Reasoning effort is optional - continue even if None
        
        return mode, (agent, selected_model, selected_reasoning)