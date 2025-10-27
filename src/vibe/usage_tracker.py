from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional


def get_config_path() -> Path:
    """Get path to vibe config directory."""
    config_dir = Path.home() / ".config" / "vibe"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_usage_path() -> Path:
    """Get path to persistent usage data."""
    return get_config_path() / "usage.json"


def get_pending_path() -> Path:
    """Get path to pending increments file."""
    return get_config_path() / "pending_increments.json"


def load_usage() -> Dict[str, Dict[str, int]]:
    """Load persistent usage data."""
    usage_path = get_usage_path()
    if not usage_path.exists():
        return {}
    
    try:
        with open(usage_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_usage(usage: Dict[str, Dict[str, int]]) -> None:
    """Save persistent usage data."""
    usage_path = get_usage_path()
    try:
        with open(usage_path, 'w') as f:
            json.dump(usage, f, indent=2)
    except IOError:
        pass  # Silently fail if we can't save


def load_pending() -> Dict:
    """Load pending increments."""
    pending_path = get_pending_path()
    if not pending_path.exists():
        return {"session_id": None, "increments": {}}
    
    try:
        with open(pending_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"session_id": None, "increments": {}}


def save_pending(pending: Dict) -> None:
    """Save pending increments."""
    pending_path = get_pending_path()
    try:
        with open(pending_path, 'w') as f:
            json.dump(pending, f, indent=2)
    except IOError:
        pass  # Silently fail


def clear_pending() -> None:
    """Clear pending increments file."""
    pending_path = get_pending_path()
    if pending_path.exists():
        try:
            pending_path.unlink()
        except IOError:
            pass


def init_session() -> str:
    """Initialize a new tracking session. Returns session ID."""
    session_id = str(uuid.uuid4())
    pending = {
        "session_id": session_id,
        "increments": {}
    }
    save_pending(pending)
    return session_id


def queue_increment(category: str, item: str, count: int = 1) -> None:
    """Queue an increment to be committed later."""
    pending = load_pending()
    
    # Initialize session if needed
    if not pending.get("session_id"):
        init_session()
        pending = load_pending()
    
    # Initialize category if needed
    if category not in pending["increments"]:
        pending["increments"][category] = {}
    
    # Increment count
    pending["increments"][category][item] = pending["increments"][category].get(item, 0) + count
    
    save_pending(pending)


def commit_usage_increments() -> None:
    """Commit pending increments to persistent usage data."""
    pending = load_pending()
    
    # Nothing to commit
    if not pending.get("increments"):
        clear_pending()
        return
    
    usage = load_usage()
    
    # Merge pending into usage
    for category, items in pending["increments"].items():
        if category not in usage:
            usage[category] = {}
        
        for item, count in items.items():
            usage[category][item] = usage[category].get(item, 0) + count
    
    save_usage(usage)
    clear_pending()


def get_sorted_by_usage(items: List[str], category: str) -> List[str]:
    """Sort items by usage frequency, most used first."""
    usage = load_usage()
    category_data = usage.get(category, {})
    
    def sort_key(item):
        # Sort by usage count (descending), then by item name
        return (-category_data.get(item, 0), item)
    
    return sorted(items, key=sort_key)


def get_usage_count(category: str, item: str) -> int:
    """Get usage count for a specific item."""
    usage = load_usage()
    return usage.get(category, {}).get(item, 0)
