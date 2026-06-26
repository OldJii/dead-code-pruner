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
_register_lang('.c',     'tree_sitter_c')
_register_lang('.h',     'tree_sitter_c')
_register_lang('.cpp',   'tree_sitter_cpp')
_register_lang('.cc',    'tree_sitter_cpp')
_register_lang('.hpp',   'tree_sitter_cpp')
_register_lang('.cxx',   'tree_sitter_cpp')
_register_lang('.go',    'tree_sitter_go')
_register_lang('.js',    'tree_sitter_javascript')
_register_lang('.jsx',   'tree_sitter_javascript')
_register_lang('.rs',    'tree_sitter_rust')
_register_lang('.swift', 'tree_sitter_swift')
_register_lang('.cs',    'tree_sitter_c_sharp')

try:
    import tree_sitter_typescript as _tst
    _LANG_REGISTRY['.ts']  = Language(_tst.language_typescript())
    _PARSERS['.ts']        = Parser(_LANG_REGISTRY['.ts'])
    _LANG_REGISTRY['.tsx'] = Language(_tst.language_tsx())
    _PARSERS['.tsx']       = Parser(_LANG_REGISTRY['.tsx'])
except (ImportError, AttributeError):
    pass

SUPPORTED_EXTS: frozenset[str] = frozenset(_LANG_REGISTRY.keys())

SKIP_DIRS = frozenset({
    '.git', 'build', '.gradle', '.idea', 'node_modules', '__pycache__',
    'docs', 'vendor', 'target', 'dist', 'out', '.build',
})

# Mutable — set by the pipeline before parsing each file.
_current_ext = '.java'
