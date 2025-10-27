from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .model_selector import select_model, select_reasoning_effort
from .output import error_exit


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


def get_usage_config_path() -> Path:
    """Get path to vibe usage config directory."""
    config_dir = Path.home() / ".config" / "vibe"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "usage.json"


def load_usage_data() -> dict:
    """Load usage data from config file."""
    config_path = get_usage_config_path()
    if not config_path.exists():
        return {"agents": {}, "modes": {}}
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"agents": {}, "modes": {}}


def save_usage_data(usage_data: dict) -> None:
    """Save usage data to config file."""
    config_path = get_usage_config_path()
    try:
        with open(config_path, 'w') as f:
            json.dump(usage_data, f, indent=2)
    except IOError:
        pass  # Silently fail if we can't save


def increment_usage(category: str, item: str) -> None:
    """Increment usage count for an item in a category."""
    usage_data = load_usage_data()
    if category not in usage_data:
        usage_data[category] = {}
    usage_data[category][item] = usage_data[category].get(item, 0) + 1
    save_usage_data(usage_data)


def sort_by_usage(items: List[str], category: str) -> List[str]:
    """Sort items by usage frequency, most used first."""
    usage_data = load_usage_data()
    category_data = usage_data.get(category, {})
    
    def sort_key(item):
        # Sort by usage count (descending), then by item name
        return (-category_data.get(item, 0), item)
    
    return sorted(items, key=sort_key)


def run_fzf_selection(options: List[str], prompt: str = "Select", multi: bool = False, category: str | None = None) -> List[str]:
    """Run fzf to let user select from options."""
    # Sort by usage if category is provided
    if category:
        options = sort_by_usage(options, category)
        
        # Add usage count to display
        usage_data = load_usage_data()
        category_data = usage_data.get(category, {})
        display_options = []
        for option in options:
            count = category_data.get(option, 0)
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
            # Track usage
            if category:
                for item in selected:
                    increment_usage(category, item)
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