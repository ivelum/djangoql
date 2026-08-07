# -*- coding: utf-8 -*-
"""
Tests for the build-time translation compiler.

``compile_catalogs`` (in the repo-root ``_translations`` module) is what turns
the source ``.po`` catalogs into binary ``.mo`` files at build time, replacing
the old ``django-admin compilemessages`` / GNU ``msgfmt`` step. The ``.mo``
files are no longer tracked in git, so this is the single source of truth for
their compilation -- used by the build backend (``_build_meta``) and CI alike.
"""

import gettext
import pathlib
import sys


# The compiler lives at the repository root, which is not on the test
# pythonpath (only test_project/ is). tests -> core -> test_project -> root.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from _translations import compile_catalogs  # noqa: E402


PO_TEMPLATE = (
    'msgid ""\n'
    'msgstr ""\n'
    '"Content-Type: text/plain; charset=UTF-8\\n"\n'
    '\n'
    'msgid "Hello"\n'
    'msgstr "Cześć"\n'
)


def _write_po(locale_root, language, body, domain='django'):
    po_path = (
        pathlib.Path(locale_root)
        / language
        / 'LC_MESSAGES'
        / ('%s.po' % domain)
    )
    po_path.parent.mkdir(parents=True, exist_ok=True)
    po_path.write_text(body, encoding='utf-8')
    return po_path


def test_compile_catalogs_produces_mo_loadable_by_stdlib_gettext(tmp_path):
    # Django reads .mo via the stdlib gettext module, so a round-trip through
    # gettext.GNUTranslations proves the .mo is byte-compatible and correct.
    locale_root = tmp_path / 'locale'
    _write_po(locale_root, 'pl', PO_TEMPLATE)

    compile_catalogs(locale_root=str(locale_root))

    mo_path = locale_root / 'pl' / 'LC_MESSAGES' / 'django.mo'
    assert mo_path.is_file()
    with open(mo_path, 'rb') as fh:
        translations = gettext.GNUTranslations(fh)
    assert translations.gettext('Hello') == 'Cześć'


def test_compile_catalogs_compiles_every_locale(tmp_path):
    locale_root = tmp_path / 'locale'
    _write_po(locale_root, 'pl', PO_TEMPLATE)
    _write_po(locale_root, 'pl', PO_TEMPLATE, domain='djangojs')
    _write_po(locale_root, 'de', PO_TEMPLATE)
    _write_po(locale_root, 'de', PO_TEMPLATE, domain='djangojs')

    compile_catalogs(locale_root=str(locale_root))

    for language in ('pl', 'de'):
        for domain in ('django', 'djangojs'):
            mo = locale_root / language / 'LC_MESSAGES' / ('%s.mo' % domain)
            assert mo.is_file(), 'missing %s.mo for %s' % (domain, language)


def _po_with_revision_date(value):
    return (
        'msgid ""\n'
        'msgstr ""\n'
        '"PO-Revision-Date: %s\\n"\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '\n'
        'msgid "Hello"\n'
        'msgstr "Cześć"\n'
    ) % value


def test_compile_catalogs_tolerates_date_only_revision_header(tmp_path):
    # gettext/msgfmt accept a date-only PO-Revision-Date; Babel parses header
    # dates strictly. The build must not break on it (our .po files use this).
    locale_root = tmp_path / 'locale'
    _write_po(locale_root, 'pl', _po_with_revision_date('2026-05-13'))

    compile_catalogs(locale_root=str(locale_root))

    mo_path = locale_root / 'pl' / 'LC_MESSAGES' / 'django.mo'
    with open(mo_path, 'rb') as fh:
        translations = gettext.GNUTranslations(fh)
    assert translations.gettext('Hello') == 'Cześć'


def test_compile_catalogs_tolerates_gettext_placeholder_date(tmp_path):
    # A fresh `django makemessages` locale ships this placeholder verbatim.
    locale_root = tmp_path / 'locale'
    _write_po(
        locale_root, 'pl', _po_with_revision_date('YEAR-MO-DA HO:MI+ZONE')
    )

    compile_catalogs(locale_root=str(locale_root))

    mo_path = locale_root / 'pl' / 'LC_MESSAGES' / 'django.mo'
    with open(mo_path, 'rb') as fh:
        translations = gettext.GNUTranslations(fh)
    assert translations.gettext('Hello') == 'Cześć'


def test_compile_catalogs_raises_when_no_po_files(tmp_path):
    # Loud failure: never silently produce a translation-less build.
    empty_root = tmp_path / 'locale'
    empty_root.mkdir()
    try:
        compile_catalogs(locale_root=str(empty_root))
    except RuntimeError:
        pass
    else:
        raise AssertionError('expected RuntimeError when no .po files exist')
