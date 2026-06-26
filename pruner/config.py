"""Configuration loading and discovery."""

import os


def find_config(config_path: str | None = None, script_dir: str | None = None) -> str | None:
    """Auto-discover a config file if none was explicitly provided."""
    if config_path:
        return config_path
    candidates = ['pruner.yaml', 'pruner.yml', 'pruner.json']
    for name in candidates:
        if os.path.exists(name):
            return name
        if script_dir:
            p = os.path.join(script_dir, name)
            if os.path.exists(p):
                return p
    return None
