"""Configuration loading, discovery, and project-boundary options."""

from dataclasses import dataclass
import os
import re

import yaml

from .analysis.project_boundary import AUTO, WORLD_MODES


@dataclass(frozen=True)
class ReplacementRule:
    """One source replacement rule.

    Iteration intentionally yields only ``pattern`` and ``value`` so existing
    integrations that unpack legacy two-tuples remain source-compatible.
    """

    pattern: str
    value: str
    kind: str = 'symbol'
    arity: int | None = None
    discard_side_effects: bool = False
    allow_unqualified: bool = False

    def __iter__(self):
        yield self.pattern
        yield self.value


def _replacement_value(value) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if value is None:
        return 'null'
    return str(value)


def _structured_rule(item: dict, *, default_kind: str) -> ReplacementRule:
    if not isinstance(item, dict):
        raise ValueError('replacement entries must be mappings')
    kind = str(item.get('kind', default_kind)).strip().lower()
    if kind in ('method', 'call'):
        kind = 'method_call'
    if kind not in ('symbol', 'method_call'):
        raise ValueError(f'unsupported replacement kind: {kind!r}')
    key = 'method' if kind == 'method_call' and 'method' in item else 'pattern'
    pattern = str(item.get(key, '')).strip()
    if not pattern:
        raise ValueError('replacement pattern must not be empty')
    arity = item.get('arity')
    if arity is not None:
        if isinstance(arity, bool) or not isinstance(arity, int) or arity < 0:
            raise ValueError('method replacement arity must be a non-negative integer')
    allow_unqualified = bool(item.get('allow_unqualified', False))
    normalized = pattern[:-2].rstrip() if pattern.endswith('()') else pattern
    if (kind == 'method_call' and '.' not in normalized
            and not allow_unqualified):
        raise ValueError(
            'unqualified method replacements require allow_unqualified: true')
    if (kind == 'symbol' and '.' not in normalized
            and not re.fullmatch(r'[A-Z][A-Z0-9_]*', normalized)
            and not allow_unqualified):
        raise ValueError(
            'unqualified non-constant symbol replacements require '
            'allow_unqualified: true')
    return ReplacementRule(
        pattern=normalized,
        value=_replacement_value(item.get('value', '')),
        kind=kind,
        arity=arity,
        discard_side_effects=bool(item.get('discard_side_effects', False)),
        allow_unqualified=allow_unqualified,
    )


def load_replacement_rules(path: str) -> list[ReplacementRule]:
    """Load symbol and Java method-call replacement rules from YAML."""
    with open(path, 'r', encoding='utf-8') as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError('configuration root must be a mapping')

    rules: list[ReplacementRule] = []
    replacements = data.get('replacements')
    if isinstance(replacements, list):
        rules.extend(_structured_rule(item, default_kind='symbol')
                     for item in replacements)
    elif replacements is not None:
        raise ValueError('replacements must be a list')
    else:
        for key, value in data.items():
            if key in ('project_boundary', 'method_replacements'):
                continue
            rules.append(_structured_rule(
                {'pattern': str(key), 'value': value},
                default_kind='symbol'))

    method_replacements = data.get('method_replacements', []) or []
    if not isinstance(method_replacements, list):
        raise ValueError('method_replacements must be a list')
    rules.extend(_structured_rule(item, default_kind='method_call')
                 for item in method_replacements)
    return rules


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
