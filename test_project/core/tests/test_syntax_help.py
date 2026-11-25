"""Tests for the Markdown-based syntax help renderer (djangoql.syntax_help).

These cover the framework-light helpers in isolation: language resolution,
file loading, image-token substitution, and the import-guarded Markdown ->
HTML / <pre> fallback. The admin view that wires them up is tested in
test_admin.py.
"""

import builtins

from django.test import SimpleTestCase
from django.utils import translation

from djangoql import syntax_help


class ResolveLanguageTest(SimpleTestCase):
    def test_exact_match(self):
        self.assertEqual('en', syntax_help.resolve_language('en'))
        self.assertEqual('pl', syntax_help.resolve_language('pl'))

    def test_unknown_falls_back_to_english(self):
        self.assertEqual('en', syntax_help.resolve_language('tlh'))
        self.assertEqual('en', syntax_help.resolve_language(None))
        self.assertEqual('en', syntax_help.resolve_language(''))

    def test_region_normalized_to_base(self):
        # Django hands out lowercase, hyphenated codes like 'pl-pl'.
        self.assertEqual('pl', syntax_help.resolve_language('pl-pl'))
        self.assertEqual('de', syntax_help.resolve_language('de-at'))

    def test_script_subtag_normalized(self):
        # zh-hans -> zh_Hans (the on-disk file code).
        self.assertEqual('zh_Hans', syntax_help.resolve_language('zh-hans'))

    def test_pt_br(self):
        self.assertEqual('pt_BR', syntax_help.resolve_language('pt-br'))


class LoadMarkdownTest(SimpleTestCase):
    def test_loads_english_source(self):
        text = syntax_help.load_markdown('en')
        self.assertIn('# DjangoQL search syntax', text)
        self.assertIn('COMPLETION_EXAMPLE_IMG', text)

    def test_every_advertised_language_loads(self):
        for code in syntax_help.AVAILABLE_LANGUAGES:
            text = syntax_help.load_markdown(code)
            self.assertTrue(text.strip(), '%s help is empty' % code)

    def test_title_follows_language(self):
        self.assertEqual(
            'DjangoQL search syntax',
            syntax_help.get_syntax_help_title('en'),
        )
        self.assertEqual(
            'Składnia zapytań DjangoQL',
            syntax_help.get_syntax_help_title('pl'),
        )


class RenderSyntaxHelpTest(SimpleTestCase):
    def test_image_token_substituted(self):
        body, _ = syntax_help.render_syntax_help('en', '/static/img.png')
        self.assertNotIn('COMPLETION_EXAMPLE_IMG', body)
        self.assertIn('/static/img.png', body)

    def test_html_path_when_markdown_available(self):
        try:
            import markdown  # noqa: F401
        except ImportError:
            self.skipTest('markdown not installed')
        body, is_html = syntax_help.render_syntax_help('en', '/x.png')
        self.assertTrue(is_html)
        # Tables and headings must compile (markdown 'tables' extension).
        self.assertIn('<table>', body)
        self.assertIn('<h2', body)

    def test_pre_fallback_when_markdown_missing(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == 'markdown':
                raise ImportError('forced')
            return real_import(name, *args, **kwargs)

        with mock_import(fake_import):
            body, is_html = syntax_help.render_syntax_help('en', '/x.png')
        self.assertFalse(is_html)
        # Raw markdown is returned verbatim (no <table> compiled).
        self.assertIn('# DjangoQL search syntax', body)
        self.assertNotIn('<table>', body)

    def test_language_selection_changes_content(self):
        try:
            import markdown  # noqa: F401
        except ImportError:
            self.skipTest('markdown not installed')
        with translation.override('pl'):
            body, _ = syntax_help.render_syntax_help(
                translation.get_language(), '/x.png'
            )
        # The Polish heading differs from the English one.
        self.assertIn('Składnia', body)


class AllLocalesStructureTest(SimpleTestCase):
    """Every advertised locale must preserve the document's structural
    invariants. This catches a broken/empty/garbled translation even though we
    cannot machine-check wording quality.
    """

    # Verbatim query examples that translators must not alter, and the image
    # token that must survive untranslated in every file.
    INVARIANTS = [
        'COMPLETION_EXAMPLE_IMG',
        'first_name = "John"',
        'groups.name in ("Marketing", "Support")',
        'last_name startswith "do"',
        'id not in (42, 9000)',
        '| --- |',
    ]

    def test_english_is_available(self):
        self.assertIn('en', syntax_help.AVAILABLE_LANGUAGES)

    def test_every_locale_keeps_invariants(self):
        for code in syntax_help.AVAILABLE_LANGUAGES:
            text = syntax_help.load_markdown(code)
            for needle in self.INVARIANTS:
                self.assertIn(needle, text, f'{code} help missing {needle!r}')

    def test_every_locale_compiles_to_two_tables(self):
        try:
            import markdown  # noqa: F401
        except ImportError:
            self.skipTest('markdown not installed')
        for code in syntax_help.AVAILABLE_LANGUAGES:
            body, is_html = syntax_help.render_syntax_help(code, '/x.png')
            self.assertTrue(is_html)
            self.assertEqual(
                2, body.count('<table>'), '%s: expected 2 tables' % code
            )
            self.assertIn('src="/x.png"', body, '%s: image not rendered' % code)


class _mock_import:
    """Context manager swapping builtins.__import__ (small local helper)."""

    def __init__(self, replacement):
        self.replacement = replacement
        self.original = None

    def __enter__(self):
        self.original = builtins.__import__
        builtins.__import__ = self.replacement
        return self

    def __exit__(self, *exc):
        builtins.__import__ = self.original


def mock_import(replacement):
    return _mock_import(replacement)
