# Translatable autocomplete operator labels (+ search placeholder)

**Date:** 2026-06-05
**Status:** Approved design, ready for implementation plan

## Problem

The DjangoQL autocomplete popup shows three English hint labels next to
operators — `is not equal to`, `contains`, `does not contain` — plus the search
box placeholder `Advanced search with Query Language`. These are not covered by
the project's `gettext` catalogs:

- The operator hints are baked into the upstream `djangoql-completion` bundle's
  `generateSuggestions`, stored as each suggestion's `suggestionText`
  (e.g. `!=<i>is not equal to</i>`). They are plain JS string literals, not
  `gettext` calls, so they cannot be translated from a consumer project (e.g.
  bpp) without intervention.
- The placeholder is a plain literal in the hand-written
  `djangoql/static/djangoql/js/completion_admin.js`.

We want all four strings translatable through the project's existing
`.po`/`.mo` workflow, for all 11 maintained locales.

## Key constraints discovered

1. **Admin's own `jsi18n` cannot be reused.** `change_list.html` already loads
   `<script src="{% url 'admin:jsi18n' %}">`, but `AdminSite.i18n_javascript`
   hard-codes `packages=["django.contrib.admin"]`. With a non-empty
   `localedirs`, `DjangoTranslation.__init__` takes the `if localedirs:` branch
   and **skips** `_add_installed_apps_translations()`, so that catalog contains
   only admin's strings — never djangoql's. We therefore need our own catalog
   endpoint.

2. **Catalogs merge, not overwrite.** Django's `JavaScriptCatalog` output merges
   entries into the shared `django.catalog` object and initializes `gettext`
   only once. So our catalog `<script>` coexists cleanly with admin's existing
   `jsi18n` on the same page; load order does not matter for correctness.

3. **A view URL can live in a static `Media` js list.** `reverse()` returns a
   root-relative path (`/admin/app/model/djangoql-i18n/`). Django's `Media`
   treats any js path starting with `/` as already-absolute (no `STATIC_URL`
   prefix), so the dynamic catalog view can be injected via `Media` without a
   template override.

4. **Only 3 operators carry hints.** The bundle renders `=`, `startswith`,
   `not startswith`, `endswith`, `not endswith`, `>`, `>=`, `<`, `<=`, `in`,
   `not in` literally. Only `!=`, `~`, `!~` have human-readable hints. So the
   operator-label set is exactly 3 strings.

5. **Build toolchain required.** `node_modules/` is absent; the wrapper change
   in `completion-widget/index.js` only reaches the shipped bundle after
   `yarn install && yarn build`. `yarn`, `node` (v26), and `msgfmt` are all
   available locally.

## Scope

**In scope — 4 strings, new `djangojs` gettext domain, 11 locales**
(`de, es, fr, it, ja, nl, pl, pt_BR, ru, uk, zh_Hans`):

- `is not equal to`
- `contains`
- `does not contain`
- `Advanced search with Query Language`

**Out of scope:** other JS UI text (syntax-help link text, toggle wiring beyond
the placeholder reuse), and any non-JS strings already handled by the `django`
domain.

## Design

### 1. Catalog endpoint (`djangoql/admin.py`)

In `DjangoQLSearchMixin.get_urls()`, inside the existing
`if self.djangoql_completion:` block, register a per-model URL:

```python
from django.views.i18n import JavaScriptCatalog

path(
    'djangoql-i18n/',
    self.admin_site.admin_view(
        JavaScriptCatalog.as_view(packages=['djangoql']),
        cacheable=True,
    ),
    name='{}_{}_djangoql_i18n'.format(
        self.model._meta.app_label,
        self.model._meta.model_name,
    ),
),
```

- `packages=['djangoql']` matches the app's `AppConfig.name` (`djangoql` is in
  `INSTALLED_APPS`). The view's domain defaults to `djangojs`.
- `admin_view(..., cacheable=True)` matches the other djangoql admin URLs
  (staff-only; the changelist is staff-only anyway) and mirrors admin's own
  cacheable `jsi18n`.

### 2. Emit the catalog `<script>` (`djangoql/admin.py` `media` property)

Prepend the reversed URL to the `js` list so `gettext` is defined before
`completion.js` runs:

```python
js = [
    reverse('{}:{}_{}_djangoql_i18n'.format(
        self.admin_site.name,
        self.model._meta.app_label,
        self.model._meta.model_name,
    )),
    'djangoql/js/completion.js',
]
```

`reverse()` is evaluated at media-render time (URLs registered, no request
needed) and yields a `/`-rooted path, so `Media` emits
`<script src="/admin/app/model/djangoql-i18n/"></script>` verbatim.

### 3. Catalog content (`djangoql/locale/<lang>/LC_MESSAGES/djangojs.po` + `.mo`)

Author a `djangojs.po` for each of the 11 locales with the 4 msgids, headers and
`Plural-Forms` mirrored from the locale's existing `django.po`. Compile with
`compilemessages` (`msgfmt`) to `djangojs.mo`.

Authored directly rather than via `makemessages`, because the source strings
live in JS files outside the app directory, and `makemessages -d djangojs`
would otherwise also scan the minified `completion.js` bundle.

All 11 locales get real translations (machine-assisted where the maintainer
does not read the language; this is a known trade-off accepted for coverage).

### 4. JS consumers

**`completion-widget/index.js` (webpack-bundled wrapper):**

- Add a guarded helper:
  `function gettext(s) { return window.gettext ? window.gettext(s) : s; }`
  — degrades to English when no catalog is present (non-admin usage).
- In the **existing** `generateSuggestions` override, within the
  `context.scope === 'comparison'` branch, remap the 3 operator hints using a
  fixed map and rebuild `suggestionText` from `s.text`:

  ```js
  var OP_HINTS = {
    '!=': 'is not equal to',
    '~': 'contains',
    '!~': 'does not contain',
  };
  // for each suggestion s in comparison scope:
  if (OP_HINTS[s.text]) {
    s.suggestionText = s.text + '<i>' + gettext(OP_HINTS[s.text]) + '</i>';
  }
  ```

  This is independent of upstream's exact markup and only touches those 3
  operators. It must run for comparison scope regardless of the existing
  `object_reference` operator filter; the remap runs first, then the filter.

**`djangoql/static/djangoql/js/completion_admin.js` (hand-written static):**

- Wrap the placeholder in the same guarded `gettext`:
  ```js
  var QLPlaceholder = window.gettext
    ? window.gettext('Advanced search with Query Language')
    : 'Advanced search with Query Language';
  ```
  (`QLToggle.title` already reuses `QLPlaceholder`, so the tooltip is covered.)
  This file ships as-is (not webpack-built), so no rebuild is needed for it.

### 5. Rebuild the bundle

`yarn install && yarn build` regenerates
`djangoql/static/djangoql/js/completion.js` (and `completion.css`) from the
updated wrapper. Verify the diff is limited to our additions plus expected
minifier churn.

### 6. Testing

- **Python (`test_project/core/tests/test_admin.py`):**
  - GET the `djangoql-i18n/` catalog URL with a non-English language activated
    (e.g. `pl`) and assert the response body contains the expected translation
    for at least one msgid (e.g. the Polish `contains`). Verifies URL
    registration, `packages`, compiled `.mo`, and catalog merge.
  - Assert the rendered `media` js list includes the reversed i18n URL.
- **JS visual behaviour:** no JS unit harness exists; verify via the existing
  `example_project` Playwright script (manual or extended), confirming the popup
  shows translated hints and placeholder under a non-English language.
- **Graceful degradation:** the guarded `gettext` fallback means a page without
  a catalog renders English — no hard dependency, no error.

## Risks / open items

- **Bundle diff noise:** a fresh `yarn install` could pull slightly different
  transitive dev deps and produce minifier churn beyond our change. Mitigation:
  review the `completion.js` diff; keep wrapper edits minimal and localized.
- **Machine translation quality** for locales the maintainer does not read
  (accepted trade-off; translators can refine the `.po` later).
- **`packages=['djangoql']` resolution:** depends on the app being importable as
  `djangoql` (confirmed in `INSTALLED_APPS`).

## Affected files

- `djangoql/admin.py` — new URL in `get_urls()`, i18n URL in `media`.
- `completion-widget/index.js` — gettext helper + operator-hint remap.
- `djangoql/static/djangoql/js/completion_admin.js` — placeholder via gettext.
- `djangoql/static/djangoql/js/completion.js` (+ `.css`) — regenerated bundle.
- `djangoql/locale/<lang>/LC_MESSAGES/djangojs.po` + `.mo` — 11 new catalogs.
- `test_project/core/tests/test_admin.py` — catalog endpoint + media tests.
