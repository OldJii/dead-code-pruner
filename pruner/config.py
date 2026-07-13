"""Configuration loading, discovery, and project-boundary options."""

import os

import yaml

from .analysis.project_boundary import AUTO, WORLD_MODES


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


def load_boundary_options(path: str) -> tuple[str, dict[str, str]]:
    """Return ``(mode, per-module overrides)`` from ``project_boundary``.

    Supported forms::

        project_boundary: auto

        project_boundary:
          mode: auto
          modules:
            ":app": closed
            ":sdk": open
    """
    with open(path, 'r', encoding='utf-8') as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return AUTO, {}
    section = data.get('project_boundary', AUTO)
    if isinstance(section, str):
        mode = section.strip().lower()
        modules = {}
    elif isinstance(section, dict):
        mode = str(section.get('mode', AUTO)).strip().lower()
        raw_modules = section.get('modules', {}) or {}
        if not isinstance(raw_modules, dict):
            raise ValueError('project_boundary.modules must be a mapping')
        modules = {
            str(name): str(world).strip().lower()
            for name, world in raw_modules.items()
        }
    else:
        raise ValueError('project_boundary must be a string or mapping')
    if mode not in WORLD_MODES:
        raise ValueError(
            f"invalid project_boundary mode {mode!r}; expected auto, closed, or open")
    invalid = {name: world for name, world in modules.items()
               if world not in WORLD_MODES - {AUTO}}
    if invalid:
        raise ValueError(
            'project_boundary module values must be closed or open: '
            + ', '.join(f'{name}={world}' for name, world in invalid.items()))
    return mode, modules
