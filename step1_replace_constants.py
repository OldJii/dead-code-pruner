#!/usr/bin/env python3
"""
Step 1: Constant replacement (skips comments and strings)

Reads replacement rules from a config file (YAML or JSON) and replaces
matching expressions in Java/Kotlin source code with boolean literals.

Config format (pruner.yaml):
  replacements:
    - pattern: "BuildConfig.IS_PRODUCTION"
      value: true
    - pattern: "FeatureFlags.isLegacyMode"
      value: false
"""
import os, re, sys, json


def _tokenize_and_replace(content, pattern, replacement):
    """Split content into (code, non-code) tokens, apply regex only to code tokens."""
    tokens = []
    i = 0
    n = len(content)
    code_start = 0

    while i < n:
        if content[i] == '/' and i+1 < n and content[i+1] == '*':
            if i > code_start:
                tokens.append(('code', content[code_start:i]))
            end = content.find('*/', i+2)
            if end == -1: end = n - 2
            tokens.append(('comment', content[i:end+2]))
            i = end + 2
            code_start = i
            continue
        if content[i] == '/' and i+1 < n and content[i+1] == '/':
            if i > code_start:
                tokens.append(('code', content[code_start:i]))
            end = content.find('\n', i)
            if end == -1: end = n
            tokens.append(('comment', content[i:end]))
            i = end
            code_start = i
            continue
        if content[i] == '"':
            if i > code_start:
                tokens.append(('code', content[code_start:i]))
            j = i + 1
            while j < n:
                if content[j] == '\\': j += 2; continue
                if content[j] == '"': j += 1; break
                j += 1
            tokens.append(('string', content[i:j]))
            i = j
            code_start = i
            continue
        if content[i] == "'":
            if i > code_start:
                tokens.append(('code', content[code_start:i]))
            j = i + 1
            while j < n:
                if content[j] == '\\': j += 2; continue
                if content[j] == "'": j += 1; break
                j += 1
            tokens.append(('char', content[i:j]))
            i = j
            code_start = i
            continue
        i += 1

    if code_start < n:
        tokens.append(('code', content[code_start:]))

    result = []
    for kind, text in tokens:
        if kind == 'code':
            text = re.sub(pattern, replacement, text)
        result.append(text)
    return ''.join(result)


def load_replacements(config_path):
    """Load replacement rules from config file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if config_path.endswith(('.yaml', '.yml')):
        try:
            import yaml
            config = yaml.safe_load(content)
        except ImportError:
            print("ERROR: PyYAML not installed. Use JSON config or: pip install pyyaml")
            sys.exit(1)
    else:
        config = json.loads(content)

    rules = []
    for r in config.get('replacements', []):
        pattern_str = r['pattern']
        value = str(r['value']).lower()
        if value not in ('true', 'false'):
            print(f"WARNING: skipping rule with non-boolean value: {pattern_str} → {value}")
            continue

        escaped = re.escape(pattern_str)
        fqn_pattern = r'[a-zA-Z_][a-zA-Z0-9_.]*\.' + escaped + r'\b'
        simple_pattern = r'\b' + escaped + r'\b'

        rules.append({
            'quick_check': pattern_str,
            'patterns': [fqn_pattern, simple_pattern],
            'value': value,
            'display': f"{pattern_str} → {value}",
        })

    return rules


def process_file(filepath, rules):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content

    for rule in rules:
        if rule['quick_check'] not in content:
            continue
        for pattern in rule['patterns']:
            content = _tokenize_and_replace(content, pattern, rule['value'])

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


SKIP_DIRS = {'.git', 'build', '.gradle', '.idea', 'node_modules', '__pycache__'}


def main():
    if len(sys.argv) < 2:
        print("Usage: step1_replace_constants.py <target> [--config pruner.yaml]")
        return

    target = sys.argv[1]
    config_path = None
    for i, arg in enumerate(sys.argv):
        if arg == '--config' and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]

    if not config_path:
        for candidate in ['pruner.yaml', 'pruner.yml', 'pruner.json']:
            if os.path.exists(candidate):
                config_path = candidate
                break
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), candidate)
            if os.path.exists(p):
                config_path = p
                break

    if not config_path:
        print("ERROR: No config file found. Create pruner.yaml or use --config")
        sys.exit(1)

    rules = load_replacements(config_path)
    if not rules:
        print("No replacement rules found in config")
        return

    print(f"Loaded {len(rules)} replacement rules:")
    for r in rules:
        print(f"  {r['display']}")

    count = 0
    if os.path.isfile(target):
        if process_file(target, rules): count = 1
    else:
        for dp, dns, fns in os.walk(target):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for f in fns:
                if f.endswith(('.java', '.kt')):
                    try:
                        if process_file(os.path.join(dp, f), rules): count += 1
                    except Exception:
                        pass
    print(f'step1: {count} files changed')
    return count


if __name__ == '__main__':
    main()
