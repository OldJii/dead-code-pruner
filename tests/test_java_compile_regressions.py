#!/usr/bin/env python3
"""Compile the Java/Lombok regression project before and after pruning."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / 'java_compile_regressions'
sys.path.insert(0, str(PROJECT_DIR))

from pruner.pipeline import run_full_pipeline  # noqa: E402


def _compile(project: Path, label: str) -> None:
    env = os.environ.copy()
    homebrew_jdk = Path(
        '/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home')
    if homebrew_jdk.exists():
        env['JAVA_HOME'] = str(homebrew_jdk)
        env['PATH'] = f"/opt/homebrew/opt/openjdk@21/bin:{env.get('PATH', '')}"
    subprocess.run(
        ['mvn', '-q', '-T', '1C', '-DskipTests', 'clean', 'compile'],
        cwd=project, env=env, check=True)
    print(f'PASS: {label} compiles')


def main() -> int:
    if shutil.which('mvn') is None:
        raise SystemExit('Maven is required for Java compile regressions')
    with tempfile.TemporaryDirectory() as tmp:
        baseline = Path(tmp) / 'baseline'
        cleaned = Path(tmp) / 'cleaned'
        shutil.copytree(FIXTURE, baseline)
        shutil.copytree(FIXTURE, cleaned)
        _compile(baseline, 'baseline')
        empty_config = cleaned / 'pruner.yaml'
        empty_config.write_text('{}\n', encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            run_full_pipeline(
                str(cleaned), config_path=str(empty_config), world='closed')
        _compile(cleaned, 'cleaned output')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
