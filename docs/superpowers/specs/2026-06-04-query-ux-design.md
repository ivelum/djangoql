# Design: Query UX for DjangoQL — multiline, pretty-print, branch counts, highlighting

Date: 2026-06-04
Branch: `feat/query-ux`

## Guiding principle

`djangoql` is a **reusable Django library**. It ships *primitives*: Python
functions, JSON endpoints, a JS tokenizer, and **structural** CSS (no colours).
Anything tied to a particular look, editor, or UX of the consuming site is the
**integrator's decision** and must be documented as such — never hard-coded into
the core. All visual flourish (colours, themes, CodeMirror, fancy panels) lives
in a dedicated `example_project/` that demonstrates the primitives.

Four independent capabilities, delivered in order on one branch, one commit per
feature, TDD for the Python parts.

---

## A. Multiline input — Shift+Enter inserts a newline

**Problem:** The bundled `completion.js` (from npm `djangoql-completion@0.6.0`)
binds `keyCode === 13` in `onKeydown` to submit the form and does **not** check
`shiftKey`. So Enter always submits and there is no way to type a newline.

**Decision:** Enter submits (good default, keep it). `Shift+Enter` inserts a
newline.

**Approach:** A new framework-agnostic file
`djangoql/static/djangoql/js/multiline.js`. It attaches a **capture-phase**
`keydown` listener to each DjangoQL textarea:

- `Shift+Enter` → insert `\n` at the caret, `preventDefault()` +
  `stopImmediatePropagation()` (so the upstream bubble-phase handler never runs
  and does not submit).
- plain `Enter` → not touched; upstream submits as before.

Capture phase runs before upstream's bubble listener, so we win without forking
the npm package or rebuilding the webpack bundle.

- Auto-enables on `textarea.djangoql`; exposes `DjangoQLMultiline.enable(el)`.
- Wired into the admin `Media` JS list (`djangoql/admin.py`) so admin gets it by
  default.

**Testing:** Python test asserts `multiline.js` is present in the admin Media.
Keyboard behaviour is verified manually in `example_project/` — vanilla JS is
not unit-tested without a browser (stated honestly, no silent gap).

---

## B. Pretty-print / formatting

**New module `djangoql/formatter.py`:**

- `serialize_node(node) -> str` — canonical one-line rendering of an AST node.
  The duplicated `_leaf_text()` in `breakdown.py` is refactored to call this
  (single source of truth for leaf rendering).
- `format_query(query, indent=2) -> str` — parse → AST → pretty multi-line
  string. Rules: top-level `and`/`or` chains break onto their own lines;
  parenthesised groups increase indentation by `indent` spaces.

Example output:

```
author.name = "X"
  and (
    year >= 2020
    or rating > 8
  )
  and published = True
```

**Endpoint `djangoql_format`** (registered alongside the existing introspect /
suggestions endpoints in `admin.py`): accepts a raw query, returns the formatted
text. This is the primitive that widgets without a JS parser can call. A
"Format" button that calls it lives in `example_project/` and the docs.

**Testing:** Full TDD on the pure `format_query()` — leaves, AND/OR chains,
nested parens, `in (...)` lists, idempotency (formatting twice == once),
round-trip (formatted query re-parses to an equal AST).

---

## C. Record count per branch (on-demand breakdown)

**Refactor `breakdown.py`:** extract the node-counting tree builder into a
reusable `explain(search, queryset, schema, max_nodes)` that **always** returns
a tree of `{label, count, role, children, truncated}`. The existing
`explain_empty()` becomes a thin wrapper that only returns the tree when the
overall result is empty (backward compatible — current admin behaviour and
tests unchanged).

**Endpoint `djangoql_explain`** (alongside introspect/suggestions): given a
search string, returns the JSON tree. Lazy, guarded by the existing
`max_nodes` budget (`DEFAULT_MAX_NODES = 50`), with `truncated` surfaced (no
silent cap). **Triggered on demand** (a button / toggle), not on every search,
to avoid N×`COUNT()` load on large tables.

The hover/panel UI is the integrator's choice; `example_project/` provides a
reference (hover tooltip + expandable tree), reusing the existing
`empty_breakdown*.html` render style.

**Testing:** TDD on `explain()` — correct per-node counts and roles
(`killer_and`, `dead_or_branch`, leaf) against seeded data; endpoint test for
the JSON shape and the `max_nodes` truncation path.

---

## D. Syntax highlighting (generic, no imposed style)

The library supports highlighting **generically** — it does not impose a colour
scheme or an editor.

**New `djangoql/static/djangoql/js/highlight.js`:**

- `DjangoQLHighlight.tokenize(text) -> [{type, value, start, end}]` — the reusable
  primitive. Integrators can feed these tokens to CodeMirror, Prism, or anything.
  Token types: `name`, `dot`, `operator`, `logical` (and/or/not/in), `bool`,
  `none`, `number`, `string`, `paren`, `comma`, `whitespace`.
- `DjangoQLHighlight.attachOverlay(textarea)` — the lightweight default: a
  transparent textarea over a highlighted `<pre>` mirror, scroll-synced.

**New `djangoql/static/djangoql/css/highlight.css`:** **structural only** —
overlay positioning and font/metrics sync, plus `.dql-tok-*` class names with
**no colours** (or trivially overridable defaults). Colours are an integrator /
`example_project` concern.

**example_project** demonstrates **both**: the lightweight overlay with a custom
palette, and a CodeMirror 6 page driven by `tokenize()`.

**Testing:** `tokenize()` is pure and gets a Node smoke test if the toolchain
allows; otherwise verified in `example_project/`. Python side: Media wiring test.
The JS-unit-test limitation is stated, not hidden.

---

## example_project/

A dedicated, runnable Django project (separate from the test harness
`test_project/`):

- `manage.py`, settings, an app `demo`.
- **Related models with lots of seed data:** e.g. `Author`, `Book`
  (`Book.author` FK), `Publisher`, maybe `Genre` (M2M) — enough rows and
  relations that branch counts, multiline queries over relations, and
  highlighting are all meaningfully demonstrable. Seed via a management command
  (`seed_demo`) generating hundreds–thousands of related rows.
- Admin using `DjangoQLSearchMixin`, plus standalone demo pages showing: a
  multiline textarea, a Format button (→ `djangoql_format`), an Explain toggle
  (→ `djangoql_explain`, rendered tree + hover), the lightweight colour overlay,
  and a CodeMirror 6 variant.
- Its own CSS/theme — this is where we "go wild".
- `README` explaining how to run it.

---

## Docs (mkdocs)

One page per feature, each explicitly separating **library primitive** from
**integrator decision**:

- `docs/multiline-queries.md`
- `docs/pretty-print.md`
- `docs/query-breakdown.md` (extends the existing empty-result-breakdown story
  with the always-on / on-demand counts)
- `docs/syntax-highlighting.md`
- `docs/example-project.md`

Add to `mkdocs.yml` nav and add `CHANGES.rst` entries per feature.

---

## Delivery

Branch `feat/query-ux` from master. Commit order:

1. multiline (`multiline.js` + admin Media + test + docs)
2. pretty-print (`formatter.py` + endpoint + breakdown refactor + tests + docs)
3. breakdown/counts (`explain()` refactor + endpoint + tests + docs)
4. highlighting (`highlight.js` + `highlight.css` + Media + docs)
5. example_project (models, seed, demo pages, CodeMirror, README) + docs nav

TDD for all Python primitives. JS verified via example_project (limitation
stated, not hidden).

## Out of scope (YAGNI)

- No forking / rebuilding the upstream `djangoql-completion` npm bundle.
- No imposed colour scheme or mandatory editor in the core library.
- No automatic per-search counting (on-demand only).
- No per-node source spans in the parser (the breakdown renders labels from the
  AST; inline hover mapping in the demo re-renders the query from the AST as
  clickable segments instead of slicing source).
