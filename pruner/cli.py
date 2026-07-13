"""CLI entry point for the tree-sitter dead-code pruner."""

import argparse
import os
import sys

from .config import find_config
from .pipeline import run_full_pipeline


def main():
    ap = argparse.ArgumentParser(
        prog='pruner',
        description='tree-sitter AST-based dead-code pruner (multi-language)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python -m pruner .                               # full pipeline, auto-find config
  python -m pruner src/ --config pruner.yaml        # explicit config
  python -m pruner . --dry-run                      # scan only, no changes
  python -m pruner . --phases 1                     # constant folding only
  python -m pruner . --phases 1,2                   # phase 1+2 only
""",
    )
    ap.add_argument('target', nargs='?', default='.',
                    help='File or directory to process (default: .)')
    ap.add_argument('--config', default=None,
                    help='Path to config file (auto-discovers pruner.yaml if omitted)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Scan and report only, do not modify files')
    ap.add_argument('--phases', default=None,
                    help='Comma-separated phases to run (default: 1,2,3)')
    ap.add_argument('--world', choices=('auto', 'closed', 'open'), default=None,
                    help='Override project-boundary detection')

    args = ap.parse_args()

    target = os.path.abspath(args.target)
    if not os.path.exists(target):
        print(f"Error: {target} does not exist", file=sys.stderr)
        sys.exit(1)

    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = find_config(args.config, script_dir)
    if not config_path:
        print("Error: no config file found. Use --config or place pruner.yaml in project root.",
              file=sys.stderr)
        sys.exit(1)

    phases = None
    if args.phases:
        phases = [int(p.strip()) for p in args.phases.split(',')]

    run_full_pipeline(
        target,
        config_path,
        dry_run=args.dry_run,
        phases=phases,
        world=args.world,
    )


if __name__ == '__main__':
    main()
