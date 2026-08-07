# Markdown-based, i18n-aware DjangoQL syntax help

Date: 2026-06-05
Status: Approved

## Problem

The admin "DjangoQL search syntax" help is a single HTML template
(`djangoql/templates/djangoql/syntax_help.html`) built from nested Django
`{% block %}` sections. The prose is buried in markup, which makes it:

- hard to translate (no clean unit of prose to hand a translator), and
- awkward to reuse outside the admin (it is tied to `admin/base_site.html`).

We want the help authored as Markdown, rendered as HTML when a Markdown
compiler is available and as `<pre>` plain text otherwise, available in all
supported languages, and reusable outside the admin (demonstrated by the
example project).

## Goals

1. Author the syntax help as Markdown (faithful conversion of today's content).
2. The admin help page renders the Markdown as HTML **if** a Markdown→HTML
   library is importable, otherwise as escaped text inside `<pre>`.
3. djangoql core must **not** declare a Markdown dependency. The example
   project declares it, so the example shows the HTML rendering.
4. Provide the help in all 11 supported languages, selected by Django's active
   language, with English fallback.

## Non-goals

- gettext/`.po` translation of the prose (rejected: painful for multi-paragraph
  documents). Translation is per-language whole-document Markdown files.
- Preserving the old per-`{% block %}` override hooks for individual content
  sections. Integrators may still override the wrapper template (chrome) and may
  point the help at their own Markdown.

## Design

### 1. Markdown sources (per-language files)

New directory `djangoql/help/` with one file per locale:

```
djangoql/help/syntax_help.en.md        # canonical source
djangoql/help/syntax_help.de.md
djangoql/help/syntax_help.es.md
djangoql/help/syntax_help.fr.md
djangoql/help/syntax_help.it.md
djangoql/help/syntax_help.ja.md
djangoql/help/syntax_help.nl.md
djangoql/help/syntax_help.pl.md
djangoql/help/syntax_help.pt_BR.md
djangoql/help/syntax_help.ru.md
djangoql/help/syntax_help.uk.md
djangoql/help/syntax_help.zh_Hans.md
```

`syntax_help.en.md` is a faithful Markdown conversion of the current template:
Search conditions, Multiple search conditions, Fields, Related models,
Comparison operators (table), Values (table).

The completion screenshot is referenced as `![DjangoQL completion
example](COMPLETION_EXAMPLE_IMG)`. `COMPLETION_EXAMPLE_IMG` is a literal token
the renderer replaces with the real `static('djangoql/img/completion_example.png')`
URL at render time, so the Markdown files carry no Django-specific syntax.

### 2. Renderer module `djangoql/syntax_help.py`

Pure, framework-light helpers (it may use `django.utils` but holds no view
logic):

- `AVAILABLE_LANGUAGES` — the set of locale codes with a Markdown file, derived
  by scanning `djangoql/help/` once at import.
- `resolve_language(lang) -> str` — normalize a Django language code to an
  available file code. Tries the exact code, then a normalized form
  (`pl-pl` → `pl`, `zh-hans` → `zh_Hans`, case-folded with `_`), then the base
  language, then `"en"`.
- `load_markdown(language) -> str` — read the resolved file's text.
- `render_syntax_help(language, image_url) -> (body: str, is_html: bool)` —
  load, substitute `COMPLETION_EXAMPLE_IMG` with `image_url`, then:
  - `try: import markdown` → `(markdown.markdown(text, extensions=[...]), True)`
    Extensions: `["tables", "fenced_code"]` (tables are required for the
    operator/value tables).
  - `except ImportError` → `(text, False)`; the template wraps it in `<pre>`
    (escaped by Django autoescaping).

This module is the single place the import guard lives, so both the admin and
the example project share identical behaviour.

### 3. Admin integration (`djangoql/admin.py`)

- Replace the `TemplateView`-based URL at `djangoql-syntax/` with a bound method
  `djangoql_syntax_help(self, request)`, wrapped in `self.admin_site.admin_view`,
  keeping the URL name `djangoql_syntax_help` and the login-redirect behaviour
  the existing test asserts (`test_admin.py::test_djangoql_syntax_help`).
- The method:
  1. `language = get_language()`
  2. `image_url = static('djangoql/img/completion_example.png')`
  3. `body, is_html = render_syntax_help(language, image_url)`
  4. render `self.djangoql_syntax_help_template` with admin context
     (`self.admin_site.each_context(request)`) plus `{body, is_html}`.
- `djangoql_syntax_help_template` is repurposed as the overridable **wrapper**
  (page chrome). New body:
  `{% if is_html %}{{ body|safe }}{% else %}<pre>{{ body }}</pre>{% endif %}`,
  inside the existing `admin/base_site.html` shell and sidebar contents.
- The old block-structured content is removed from the wrapper template.

### 4. djangoql core: no Markdown dependency

`markdown` is **not** added to `[project.dependencies]`. Without it the admin
help shows raw Markdown in `<pre>`. With it (installed for any reason) the help
renders as HTML automatically — no djangoql configuration required.

### 5. example_project: Markdown installed + HTML help shown

- New `example_project/requirements.txt` declaring `markdown` (plus an editable
  install of the local djangoql and a Django pin, matching how the example is
  run).
- New public (non-admin) view at `syntax-help/` (`views.syntax_help`) that calls
  `render_syntax_help(get_language(), static(...))` and renders the compiled
  HTML in the demo's own `base.html` chrome.
- A nav link to it in `example_project/library/templates/library/base.html`.

This is the concrete "display HTML markdown help there" deliverable: because the
example installs `markdown`, both its admin help page and this public page show
HTML.

### 6. i18n behaviour

Language is chosen from Django's active language (set by `LocaleMiddleware`,
`?language=`, or `translation.override`). Unknown/unsupported languages fall
back to English via `resolve_language`. All 11 translations are written now.

### Packaging

Add `"help/**/*.md"` to `[tool.setuptools.package-data]` under `djangoql` so the
Markdown ships in the wheel and sdist.

## Testing (`test_project/core/tests`)

- `resolve_language`: exact match; normalization (`pl-pl`→`pl`,
  `zh-hans`→`zh_Hans`); base-language fold; unknown → `en`.
- `render_syntax_help`: image token is substituted; HTML path returns
  `is_html=True` and contains `<table>`/`<h2>` when `markdown` is importable;
  `<pre>` path returns `is_html=False` when `markdown` import is forced to fail
  (monkeypatch `builtins.__import__` or `sys.modules`).
- Admin view: preserves the auth redirect (302 unauthenticated, 200
  authenticated) under both apps (`admin`, `zaibatsu`); response varies with
  active language (e.g. a Polish heading appears under
  `translation.override("pl")`).
- Every advertised locale file exists and is non-empty, and the comparison
  operator/value tables are present in each (structural smoke check on the
  Markdown, not a translation-quality check).

## Risks / mitigations

- **Translation quality** for languages the team can't verify — mitigated by a
  structural smoke test (headings, tables, code fences, image token present in
  every file) so a broken/empty translation fails CI even if wording can't be
  machine-checked.
- **Markdown extension availability** — `tables` and `fenced_code` are bundled
  with the `markdown` package (no extra installs), so the import guard alone is
  sufficient.
