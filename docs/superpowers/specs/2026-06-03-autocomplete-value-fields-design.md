# B — Autocomplete value fields (pluggable, DAL-friendly)

Date: 2026-06-03
Status: **Approved for implementation.**

## Problem

DjangoQL can already suggest **values** for `choices` fields and for string
columns (`StrField.get_options` does a DB `icontains`). What's missing is a clean
way to let a field's value suggestions come from an **arbitrary source** — most
importantly an existing **django-autocomplete-light (DAL)** endpoint the project
already has — so the user can pick an object (e.g. an author) and filter by it,
without writing new endpoints and without forking the completion widget.

The user picks a row from autocomplete; the query must filter unambiguously even
across 50k+ rows with duplicate display names.

## Hard constraint

The completion widget is the upstream `djangoql-completion` npm package
(re-bundled in `completion-widget/index.js`), **not** in this repo. Therefore:

- **No JS changes.** Everything happens server-side, through the existing async
  value-suggestion path: the widget calls one generic
  `suggestions_api_url?field=<model>.<field>&search=<prefix>&page=N`, and
  `SuggestionsAPIView` answers it via `field.get_options(search)`.
- The widget inserts the chosen suggestion **verbatim, as a quoted string**, and
  shows the same string it inserts. So the server fully controls the inserted
  text, and **display == inserted** (consequence: any embedded id is visible).

## Decisions

- **Identity via embedded id.** Suggestions are formatted `"<label> [<id>]"`
  (e.g. `Jan Kowalski [49990]`). `get_lookup_value` parses the trailing `[\d+]`
  → integer pk; the field filters `<fk> = pk`. Unambiguous, scales, readable.
- **The FK is exposed as a value field** (a picker), so under that name you do
  **not** also traverse `autor.name`. Need both → use a second field name.
- **Three providers** (priority high→low) for where suggestions come from:
  1. `url` — an existing DAL endpoint (url name or local path).
  2. `queryset` / callable (`search -> queryset`) — DAL-agnostic, full control.
  3. subclass override of `get_options()` / `format_label()` / `get_id()`.
- **URL provider calls the view in-process**, not over HTTP: `resolve(path)` →
  view, called with the **current authenticated request** (GET param `q` set to
  the search term). This reuses the DAL view's queryset, permissions, and
  per-user filtering for free, with no network round-trip or cookie forwarding.
- `[id]` is visible in the drop-down and query (accepted by the user).

## Out of scope (would require forking the widget or more)

- Rich drop-down rows (icons/images/HTML), or **hiding** the `[id]` from display.
- Widget calling a DAL endpoint **directly** (Select2 format client-side).
- Deep pagination / infinite scroll against DAL (v1 returns one top-N page).
- External (non-local, unresolvable) URLs — use `queryset` for those.
- Grouped (optgroup) DAL results — v1 handles a flat `results` list.

## Architecture

### `AutocompleteField(StrField)` (in `djangoql/extras.py`)

- `suggest_options = True`; async (no static model choices → `async_options`
  True), so the serializer emits `options: true` and the widget fetches via the
  existing endpoint. **No serializer change needed.**
- Config (kwargs or schema-map): `url`, `queryset`/`get_queryset`,
  `search_fields`, `view`, `label` (callable obj→str, default `str`),
  `id_of` (callable obj→id, default `obj.pk`), `search_param` (default `q`),
  `limit` (default 50).
- Overridable methods: `get_options(search)`, `get_queryset(search)`,
  `format_label(obj)`, `get_id(obj)`, `parse_id(value)`.
- `get_options(search)`:
  - strip a trailing `[\d+]` from `search` (so re-editing an existing
    `"Label [42]"` searches by `Label`);
  - resolve provider → produce up to `limit` strings `"<label> [<id>]"`;
  - URL provider: `resolve(urlsplit(url).path)`, clone the bound request with
    `GET = {search_param: search}`, call the view, `json.loads` the response,
    map `results[] -> f'{strip_tags(text)} [{id}]'`.
- `get_lookup_value(value)`: parse trailing `[\d+]` → `int`; handle a list (for
  `in`); if no bracket, return the raw string (free-text fallback).
- `get_lookup(path, operator, value)`: when an id was parsed, filter
  `'__'.join(path + [name]) <op> = pk`; otherwise fall back to an `icontains`
  over `search_fields` (so partially-typed free text still filters).
- `validate(value)`: accept `str`.

### Request threading (in `djangoql/views.py`)

`SuggestionsAPIView.get_suggestions` currently calls `field.get_options(search)`
with no request. Add a non-breaking hook: if the field exposes
`set_request(request)` (only `AutocompleteField` does), call it first. Base
fields are unaffected.

### `AutocompleteSchemaMixin` + `autocomplete` map (sugar)

```python
class RecordSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    autocomplete = {
        Record: {
            'autor':    {'url': 'autocomplete-autor'},
            'redaktor': {'queryset': lambda s: User.objects.filter(
                            public=True, last_name__icontains=s)[:50]},
        },
    }
```

- Override `get_field_instance(model, field_name)`: if `field_name` is in
  `self.autocomplete[model]`, build an `AutocompleteField` from the config
  (a dict, an `AutocompleteField` instance, or a callable) instead of the
  default field/relation.
- Include `AutocompleteSchemaMixin` in `ExtrasSchema` so the batteries-included
  schema gets it too; it also works standalone.

## Files to change

- `djangoql/extras.py` — `AutocompleteField`, `AutocompleteSchemaMixin`, add to
  `ExtrasSchema`.
- `djangoql/views.py` — optional `set_request` hook in `get_suggestions`.
- `test_project/` — a small DAL-style autocomplete endpoint + url for URL-mode
  tests (returns Select2 JSON `{results:[{id,text}], pagination:{more}}`).
- `docs/` — new page "Integrating django-autocomplete-light" + link in nav.
- `CHANGES.rst` — feature entry (additive, non-breaking).

## Test plan (TDD)

- `parse_id`: `"X [42]"` → 42; `["A [1]", "B [2]"]` → [1, 2]; `"plain"` → "plain".
- queryset provider: `get_options("kow")` returns `"<label> [<pk>]"` strings,
  capped at `limit`.
- query filters by pk: `autor = "Jan Kowalski [42]"` → `WHERE autor_id = 42`
  (and `!=`, `in`).
- free-text fallback: `autor = "kowal"` (no bracket) → `icontains` over
  `search_fields`.
- URL provider: a fake DAL endpoint in `test_project` returns Select2 JSON;
  `AutocompleteField(url=...)` resolves + calls it in-process with `q`, formats
  `"text [id]"`, and the query filters by pk; the bound request reaches the view.
- map/mixin: `autocomplete` config produces an `AutocompleteField`; serialized
  schema has `options: true` for it; the FK is a value field (not a relation).
- serializer: `AutocompleteField` is async → `options: true` with a
  suggestions URL present.

## Future work

- Deep pagination / infinite scroll mapped to DAL `page`.
- Optional opt-in self-HTTP for external/remote URLs (with cookie forwarding).
- Widget-side enhancements (rich rows, hidden id) — needs a vendored widget.
- Per-request/per-user beyond static querysets is already reachable via the
  threaded request; document patterns.
