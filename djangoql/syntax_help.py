"""Render the DjangoQL syntax help from per-language Markdown files.

The help text lives as one Markdown document per language under
``djangoql/help/syntax_help.<code>.md``. This module turns the active language
into a concrete file and renders it, compiling to HTML **only if** a Markdown
library is importable. djangoql itself does not depend on ``markdown``; when it
is absent the raw Markdown is returned for ``<pre>`` display. Installing
``markdown`` (as the example project does) upgrades the output to HTML with no
further configuration.

The Markdown files carry no Django-specific syntax. The single dynamic value -
the completion screenshot URL - is written as the literal token
``COMPLETION_EXAMPLE_IMG`` and substituted here, so the documents stay portable
and translator-friendly.
"""

import os
from pathlib import Path


HELP_DIR = Path(__file__).resolve().parent / 'help'
_PREFIX = 'syntax_help.'
_SUFFIX = '.md'

#: Token in the Markdown replaced with the real completion-screenshot URL.
IMAGE_TOKEN = 'COMPLETION_EXAMPLE_IMG'

#: Markdown extensions needed to compile the operator/value tables and the
#: fenced query examples. Both ship with the ``markdown`` package itself, so the
#: import guard in :func:`render_syntax_help` is the only dependency check.
MARKDOWN_EXTENSIONS = ['tables', 'fenced_code']

DEFAULT_LANGUAGE = 'en'


def _discover_languages():
    codes = []
    for name in os.listdir(HELP_DIR):
        if name.startswith(_PREFIX) and name.endswith(_SUFFIX):
            codes.append(name[len(_PREFIX) : -len(_SUFFIX)])
    return sorted(codes)


#: Language codes that have a Markdown file on disk (e.g. ``en``, ``pt_BR``,
#: ``zh_Hans``), discovered once at import time.
AVAILABLE_LANGUAGES = _discover_languages()

# Map a normalized (lowercased, underscored) code to its canonical on-disk code
# so Django's ``pt-br`` / ``zh-hans`` resolve to ``pt_BR`` / ``zh_Hans``.
_LOOKUP = {code.lower().replace('-', '_'): code for code in AVAILABLE_LANGUAGES}


def resolve_language(lang):
    """Map a Django language code to an available help file code.

    Tries the exact (normalized) code, then the base language (``pl-pl`` ->
    ``pl``, ``de-at`` -> ``de``), then falls back to English. Always returns a
    code that has a file on disk.
    """
    if not lang:
        return DEFAULT_LANGUAGE
    key = lang.lower().replace('-', '_')
    if key in _LOOKUP:
        return _LOOKUP[key]
    base = key.split('_')[0]
    if base in _LOOKUP:
        return _LOOKUP[base]
    return DEFAULT_LANGUAGE


def load_markdown(language):
    """Return the raw Markdown for the best-matching ``language``."""
    code = resolve_language(language)
    path = HELP_DIR / (_PREFIX + code + _SUFFIX)
    return path.read_text(encoding='utf-8')


def get_syntax_help_title(language):
    """Return the first Markdown H1 for the best-matching ``language``."""
    for line in load_markdown(language).splitlines():
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    return 'DjangoQL search syntax'


def render_syntax_help(language, image_url):
    """Render the syntax help for ``language``.

    Substitutes the completion-screenshot token with ``image_url``, then returns
    ``(body, is_html)``:

    - ``(compiled_html, True)`` when a Markdown library is importable;
    - ``(raw_markdown, False)`` otherwise, for ``<pre>`` display.
    """
    text = load_markdown(language).replace(IMAGE_TOKEN, image_url)
    try:
        import markdown
    except ImportError:
        return text, False
    return markdown.markdown(text, extensions=MARKDOWN_EXTENSIONS), True
