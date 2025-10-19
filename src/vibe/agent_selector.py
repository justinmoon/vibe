from __future__ import annotations

import subprocess
from typing import List, Optional, Tuple

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
        return ["claude", "codex", "amp", "oc"]
    
    agents = []
    for agent_file in agents_dir.glob("*.md"):
        agents.append(agent_file.stem)
    
    # Add known agents that might not have .md files
    for agent in ["amp", "oc"]:
        if agent not in agents:
            agents.append(agent)
    
    return sorted(agents)


def run_fzf_selection(options: List[str], prompt: str = "Select", multi: bool = False) -> List[str]:
    """Run fzf to let user select from options."""
    try:
        cmd = ["fzf", "--prompt", f"{prompt}: "]
        if multi:
            cmd.extend(["--multi"])
        
        result = subprocess.run(
            cmd,
            input="\n".join(options),
            text=True,
            capture_output=True,
        )
        
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
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
    
    selected = run_fzf_selection(agents, "Select agent")
    return selected[0] if selected else None


def select_agents_for_duo() -> Optional[Tuple[str, str]]:
    """Prompt user to select two agents for duo mode."""
    agents = get_available_agents()
    if not agents:
        error_exit("No agents found")
        return None
    
    selected = run_fzf_selection(agents, "Select first agent", multi=False)
    if not selected:
        return None
    
    first_agent = selected[0]
    remaining_agents = [a for a in agents if a != first_agent]
    
    selected_second = run_fzf_selection(remaining_agents, "Select second agent", multi=False)
    if not selected_second:
        return None
    
    return (first_agent, selected_second[0])


def select_agent_mode() -> Optional[str]:
    """Prompt user to select agent mode (single, duo, review)."""
    modes = [
        ("single", "Single agent - Work with one AI agent"),
        ("duo", "Duo mode - Work with two agents in parallel"),
        ("review", "Review mode - Review existing duo work"),
    ]
    
    mode_options = [f"{mode} - {desc}" for mode, desc in modes]
    selected = run_fzf_selection(mode_options, "Select mode")
    
    if not selected:
        return None
    
    # Extract the mode name from the selection
    return selected[0].split(" - ")[0]


def prompt_agent_selection() -> Optional[Tuple[str, Optional[Tuple[str, str]]]]:
    """
    Main function to prompt for agent selection.
    Returns: (mode, duo_agents) where mode is 'single', 'duo', or 'review'
            and duo_agents is None for single/review, or (agent1, agent2) for duo
    """
    mode = select_agent_mode()
    if not mode:
        return None
    
    if mode == "duo":
        duo_agents = select_agents_for_duo()
        if not duo_agents:
            return None
        return mode, duo_agents
    else:
        # For single and review modes, select the primary agent
        agent = select_single_agent()
        if not agent:
            return None
        return mode, None