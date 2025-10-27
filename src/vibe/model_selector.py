from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Optional

from .output import error_exit


def get_config_path() -> Path:
    """Get path to vibe config directory."""
    config_dir = Path.home() / ".config" / "vibe"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "models.json"


def load_model_usage() -> dict:
    """Load model usage data from config file."""
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_model_usage(usage_data: dict) -> None:
    """Save model usage data to config file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w') as f:
            json.dump(usage_data, f, indent=2)
    except IOError as e:
        error_exit(f"Failed to save model usage: {e}")


def increment_model_usage(model: str) -> None:
    """Increment usage count for a model."""
    usage_data = load_model_usage()
    usage_data[model] = usage_data.get(model, 0) + 1
    save_model_usage(usage_data)


def get_available_models(agent: str = "oc") -> List[str]:
    """Get list of available models for specified agent."""
    if agent == "oc":
        try:
            result = subprocess.run(
                ["opencode", "models"],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse model names from output
            models = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    models.append(line.strip())
            return models
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to common models if opencode is not available
            return [
                "opencode/gpt-5",
                "opencode/claude-sonnet-4-5",
                "opencode/claude-opus-4-1",
                "opencode/gpt-5-codex",
                "openai/gpt-5",
                "openai/gpt-4o",
                "anthropic/claude-3-5-sonnet-20241022",
            ]
    elif agent == "codex":
        return [
            "gpt-5-codex",
            "gpt-5",
        ]
    elif agent == "droid":
        return [
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-1-20250805",
            "claude-haiku-4-5-20251001",
            "gpt-5-codex",
            "gpt-5-2025-08-07",
            "glm-4.6",
        ]
    else:
        return []


def sort_models_by_usage(models: List[str]) -> List[str]:
    """Sort models by usage frequency, most used first."""
    usage_data = load_model_usage()
    
    def sort_key(model):
        # Sort by usage count (descending), then by model name
        return (-usage_data.get(model, 0), model)
    
    return sorted(models, key=sort_key)


def select_model(agent: str = "oc") -> Optional[str]:
    """Prompt user to select a model for specified agent using fzf."""
    models = get_available_models(agent)
    if not models:
        error_exit(f"No models found for {agent}")
        return None
    
    # Sort by usage frequency
    sorted_models = sort_models_by_usage(models)
    
    # Add usage count to display
    usage_data = load_model_usage()
    display_models = []
    for model in sorted_models:
        count = usage_data.get(model, 0)
        if count > 0:
            display_models.append(f"{model} (used {count} times)")
        else:
            display_models.append(model)
    
    try:
        result = subprocess.run(
            ["fzf", "--prompt", f"Select {agent} model: "],
            input="\n".join(display_models),
            text=True,
            capture_output=True,
        )
        
        if result.returncode == 0:
            selected_display = result.stdout.strip()
            # Extract model name from display (remove usage count if present)
            selected_model = selected_display.split(" (used")[0]
            increment_model_usage(selected_model)
            return selected_model
        else:
            return None
    except FileNotFoundError:
        error_exit("Error: fzf not found. Please install fzf to use model selection.")
        return None


def select_oc_model() -> Optional[str]:
    """Prompt user to select a model for oc agent using fzf."""
    return select_model("oc")


def get_reasoning_effort_options(model: str, agent: str = "droid") -> List[str]:
    """Get reasoning effort options for a given model and agent."""
    # gpt-5-codex: supports reasoning in codex CLI, but not in droid CLI
    if model == "gpt-5-codex":
        if agent == "codex":
            return [
                "low - Fastest responses with limited reasoning",
                "medium - Dynamically adjusts reasoning based on the task (default)",
                "high - Maximizes reasoning depth for complex or ambiguous problems",
            ]
        else:
            return []
    elif model == "gpt-5":
        return [
            "minimal - Fastest responses with little reasoning",
            "low - Balances speed with some reasoning",
            "medium - Solid balance of reasoning depth and latency (default)",
            "high - Maximizes reasoning depth for complex or ambiguous problems",
        ]
    elif "claude-sonnet" in model or "claude-opus" in model or "claude-haiku" in model:
        return [
            "off - No extended thinking, faster responses (default)",
            "low - Brief consideration, balanced speed and depth",
            "medium - Moderate thinking time for complex decisions",
            "high - Deep analysis for critical architectural choices",
        ]
    elif "gpt-5" in model and model != "gpt-5-codex":
        return [
            "low - Fastest responses with some reasoning",
            "medium - Solid balance of reasoning depth and latency (default)",
            "high - Maximizes reasoning depth for complex or ambiguous problems",
        ]
    return []


def select_reasoning_effort(model: str, agent: str = "droid") -> Optional[str]:
    """Prompt user to select reasoning effort for a model using fzf."""
    options = get_reasoning_effort_options(model, agent)
    if not options:
        return None
    
    try:
        result = subprocess.run(
            ["fzf", "--prompt", f"Select reasoning effort for {model}: "],
            input="\n".join(options),
            text=True,
            capture_output=True,
        )
        
        if result.returncode == 0:
            selected_display = result.stdout.strip()
            # Extract effort level (first word before " - ")
            effort = selected_display.split(" - ")[0].split(" ")[0]
            return effort
        else:
            return None
    except FileNotFoundError:
        error_exit("Error: fzf not found. Please install fzf to use reasoning effort selection.")
        return None