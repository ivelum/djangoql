"""Compile gettext ``.po`` catalogs to binary ``.mo`` with Babel.

This is the single source of truth for turning the source ``.po`` catalogs
into the ``.mo`` files Django loads at runtime. It depends only on Babel
(pure Python) -- no GNU gettext (``msgfmt``) binary is required anywhere.

Consumers:
* the in-tree build backend (``_build_meta``), before building wheel/sdist;
* CI, which calls ``compile_catalogs()`` before running the test suite;
* developers, who run the same one-liner instead of ``compilemessages``.

The ``.mo`` files are intentionally not tracked in git.
"""

import io
import os.path
import re
import warnings
from glob import glob


# Babel parses the PO-Revision-Date / POT-Creation-Date header values strictly,
# while gettext/msgfmt (and therefore Django) ignore them. A date-only value
# (e.g. "2026-05-13") makes Babel's read_po raise ValueError. These headers are
# purely informational and absent from the runtime .mo, so when parsing fails
# we drop them and retry rather than break the build. Matches one physical
# header line, e.g. `"PO-Revision-Date: 2026-05-13\n"` plus its newline.
_DATE_HEADER_RE = re.compile(
    rb'^"(?:PO-Revision-Date|POT-Creation-Date):[^"]*"\r?\n',
    re.MULTILINE,
)


def _read_catalog(read_po, po_path):
    with open(po_path, 'rb') as fh:
        raw = fh.read()
    try:
        return read_po(io.BytesIO(raw))
    except ValueError as exc:
        # Likely an unparseable date header; strip those headers and retry.
        # If the retry still fails, the error propagates (never swallowed).
        warnings.warn(
            '%s: could not parse header (%s); dropping PO-Revision-Date / '
            'POT-Creation-Date headers for compilation' % (po_path, exc),
            stacklevel=2,
        )
        return read_po(io.BytesIO(_DATE_HEADER_RE.sub(b'', raw)))


def compile_catalogs(locale_root='djangoql/locale'):
    """Compile each ``*.po`` under *locale_root* to a sibling ``.mo`` file.

    Raises ``RuntimeError`` when there are no catalogs to compile -- we never
    want to silently produce a build without translations.
    """
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    po_files = glob(os.path.join(locale_root, '*', 'LC_MESSAGES', '*.po'))
    if not po_files:
        raise RuntimeError(
            'No .po catalogs found under %r; refusing to build without '
            'translations' % locale_root
        )
    for po_path in po_files:
        catalog = _read_catalog(read_po, po_path)
        mo_path = os.path.splitext(po_path)[0] + '.mo'
        with open(mo_path, 'wb') as fh:
            write_mo(fh, catalog)
