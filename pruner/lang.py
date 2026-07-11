"""Language registry — maps file extensions to tree-sitter parsers.

Adding a new language requires only:
  1. pip install tree-sitter-xxx
  2. Add one _register_lang() call below.
"""

from tree_sitter import Language, Parser

_LANG_REGISTRY: dict[str, Language] = {}
_PARSERS: dict[str, Parser] = {}


def _register_lang(ext: str, module_name: str, lang_func_name: str = 'language'):
    try:
        mod = __import__(module_name)
        lang = Language(getattr(mod, lang_func_name)())
        _LANG_REGISTRY[ext] = lang
        _PARSERS[ext] = Parser(lang)
    except (ImportError, AttributeError):
        pass


_register_lang('.java',  'tree_sitter_java')
_register_lang('.kt',    'tree_sitter_kotlin')
_register_lang('.kts',   'tree_sitter_kotlin')
_register_lang('.go',    'tree_sitter_go')
_register_lang('.swift', 'tree_sitter_swift')
_register_lang('.dart',  'tree_sitter_dart')

SUPPORTED_EXTS: frozenset[str] = frozenset(_LANG_REGISTRY.keys())

SKIP_DIRS = frozenset({
    '.git', 'build', '.gradle', '.idea', 'node_modules', '__pycache__',
    'docs', 'vendor', 'target', 'dist', 'out', '.build',
})

# Mutable — set by the pipeline before parsing each file.
_current_ext = '.java'
