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


def get_available_models() -> List[str]:
    """Get list of available models from opencode."""
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


def sort_models_by_usage(models: List[str]) -> List[str]:
    """Sort models by usage frequency, most used first."""
    usage_data = load_model_usage()
    
    def sort_key(model):
        # Sort by usage count (descending), then by model name
        return (-usage_data.get(model, 0), model)
    
    return sorted(models, key=sort_key)


def select_oc_model() -> Optional[str]:
    """Prompt user to select a model for oc agent using fzf."""
    models = get_available_models()
    if not models:
        error_exit("No models found")
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
            ["fzf", "--prompt", "Select model: "],
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