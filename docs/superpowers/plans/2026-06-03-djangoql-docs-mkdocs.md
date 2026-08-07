# DjangoQL MkDocs Documentation Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-file README as the primary documentation source with a MkDocs (Material) site under `docs/`, in English, logically organized, covering everything currently in README plus a new page for the derived-fields feature.

**Architecture:** MkDocs + Material theme. `docs_dir = docs`, with `docs/superpowers/` (process artifacts: specs/plans) excluded from the built site via `exclude_docs`. Content from the current `README.md` is split into focused pages; a new `derived-fields.md` documents the date/time parts, relation aggregates, and `suggested` flag shipped in the previous plan. README is trimmed to an overview that links to the site.

**Tech Stack:** MkDocs, mkdocs-material, Python 3.10+, uv. (No application code changes.)

**Reference spec:** `docs/superpowers/specs/2026-06-03-djangoql-derived-fields-design.md` (Component 4).

**Source material:** the current `README.md` (554 lines). Section headers and their line ranges (verify with `grep -n '^#' README.md` before editing, line numbers may drift):
- `# DjangoQL` (1) — title + badges + screenshot
- `## Contents` (29) — TOC (will be dropped; nav replaces it)
- `## Features` (43)
- `## Supported versions` (54)
- `## Installation` (63)
- `## Add it to your Django admin` (87)
- `## Using DjangoQL with the standard Django admin search` (104)
- `## Internationalization (i18n)` (125)
- `## Language reference` (145)
- `## DjangoQL Schema` (161)
- `## Custom search fields` (191)
- `## Can I use it outside of Django admin?` (372)
- `## Using completion widget outside of Django admin` (441)
- `## Supported by` (546)
- `## License` (552)

**Build/verify command:** `uv run mkdocs build --strict` (must succeed with no warnings). Serve locally for manual check: `uv run mkdocs serve`.

---

## Page / nav structure (target)

```
docs/
  index.md            # intro, badges, screenshot, Features, Supported versions, Supported by, License
  installation.md     # Installation
  admin.md            # Add it to your Django admin; standard-search toggle; admin completion
  language.md         # Language reference (operators, logic, literals, dot navigation)
  schema.md           # DjangoQL Schema + Custom search fields (get_fields, include/exclude,
                      #   suggest_options, get_lookup_name/get_lookup_value/get_lookup, annotations)
  derived-fields.md   # NEW: date/time parts, relation aggregates, suggested flag, ExtrasSchema
  queryset.md         # Using DjangoQL outside the admin (DjangoQLQuerySet / apply_search)
  completion-widget.md# Using the completion widget outside of Django admin
  i18n.md             # Internationalization
  superpowers/        # EXCLUDED from the built site (specs/plans live here)
```

`mkdocs.yml` `nav:` lists the pages in the order above (index first).

---

## Task 1: MkDocs scaffold + dependencies

**Files:**
- Modify: `pyproject.toml` (`[project.optional-dependencies] dev`)
- Create: `mkdocs.yml`
- Create: `docs/index.md` (minimal placeholder; filled in Task 2)
- Modify: `uv.lock` (via uv sync)

- [ ] **Step 1: Add docs dependencies**

In `pyproject.toml`, `[project.optional-dependencies] dev`, add:
```
    "mkdocs",
    "mkdocs-material",
```
Then sync: `uv sync --extra dev` (matches the repo's existing convention; there is a `uv.lock`).

- [ ] **Step 2: Create a minimal `docs/index.md` placeholder**

```markdown
# DjangoQL

Advanced search language for Django.

(Documentation site — content added in subsequent steps.)
```

- [ ] **Step 3: Create `mkdocs.yml`**

```yaml
site_name: DjangoQL
site_description: Advanced search language for Django, with Django admin integration.
repo_url: https://github.com/iplweb/djangoql-iplweb
docs_dir: docs

# Process artifacts (design specs / implementation plans) live under
# docs/superpowers/ and must not be part of the published site.
exclude_docs: |
  superpowers/

theme:
  name: material
  features:
    - navigation.sections
    - content.code.copy
    - toc.integrate

markdown_extensions:
  - admonition
  - toc:
      permalink: true
  - pymdownx.highlight
  - pymdownx.superfences

nav:
  - Home: index.md
  - Installation: installation.md
  - Django admin: admin.md
  - Language reference: language.md
  - Schema & custom fields: schema.md
  - Derived fields: derived-fields.md
  - Outside the admin: queryset.md
  - Completion widget: completion-widget.md
  - Internationalization: i18n.md
```

Note: the `nav` references pages created in Tasks 2–3. Until they exist, `--strict` will fail, so the build verification in this task uses a NON-strict build that only confirms config validity and the exclusion. The strict build is enforced in Task 4.

- [ ] **Step 4: Verify config + exclusion (non-strict)**

Run: `uv run mkdocs build -d /tmp/mkdocs_site_t1 2>&1 | tail -20`
Expected: build completes (may warn about nav pages not yet existing). Then confirm `superpowers/` was NOT rendered:
Run: `test ! -e /tmp/mkdocs_site_t1/superpowers && echo "superpowers excluded OK" || echo "FAIL: superpowers present"`
Expected: `superpowers excluded OK`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock mkdocs.yml docs/index.md
git commit -m "docs: scaffold MkDocs (Material) site; exclude superpowers/ from build"
```

---

## Task 2: Migrate README content into pages

**Files:**
- Create: `docs/index.md` (overwrite placeholder), `docs/installation.md`, `docs/admin.md`, `docs/language.md`, `docs/schema.md`, `docs/queryset.md`, `docs/completion-widget.md`, `docs/i18n.md`
- Read source: `README.md`

This task moves existing English content; it does not invent new prose. Read `README.md` and distribute its sections per the mapping below, adjusting only headings, intra-doc links, and image paths.

- [ ] **Step 1: Read the source**

Run: `grep -n '^#' README.md` to get current section line numbers, then read each section you are about to move.

- [ ] **Step 2: Create the pages by moving sections**

For each target page, copy the corresponding README section(s) verbatim, then: (a) demote the top section heading to the page H1 (single `#` per page), (b) fix any in-page anchor links (`[x](#section)`) to point to the right page (`[x](schema.md#section)`), (c) fix image/asset paths so they resolve from `docs/` (e.g. a README image at `completion-widget/...` or an external asset URL — keep absolute URLs as-is; for repo-relative images, point to the raw GitHub URL already used in README or copy the asset under `docs/assets/` and reference it).

Mapping:
- `docs/index.md` ← `# DjangoQL` intro + badges + screenshot, `## Features`, `## Supported versions`, `## Supported by`, `## License`. Drop the old `## Contents` TOC (the site nav replaces it). Add a short sentence linking onward to Installation.
- `docs/installation.md` ← `## Installation`.
- `docs/admin.md` ← `## Add it to your Django admin` + `## Using DjangoQL with the standard Django admin search`.
- `docs/language.md` ← `## Language reference`.
- `docs/schema.md` ← `## DjangoQL Schema` + `## Custom search fields`.
- `docs/queryset.md` ← `## Can I use it outside of Django admin?`.
- `docs/completion-widget.md` ← `## Using completion widget outside of Django admin`.
- `docs/i18n.md` ← `## Internationalization (i18n)`.

- [ ] **Step 3: Verify the build (non-strict, then check pages render)**

Run: `uv run mkdocs build -d /tmp/mkdocs_site_t2 2>&1 | tail -30`
Expected: builds; the only acceptable remaining warning is the not-yet-created `derived-fields.md` (added in Task 3). Confirm each migrated page produced an HTML file:
Run: `for p in index installation admin language schema queryset completion-widget i18n; do test -e /tmp/mkdocs_site_t2/$p/index.html && echo "$p OK" || echo "$p MISSING"; done`
Expected: all `OK`.

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs: migrate README sections into MkDocs pages"
```

---

## Task 3: Author the Derived fields page

**Files:**
- Create: `docs/derived-fields.md`
- Read source: `djangoql/extras.py`, `docs/superpowers/specs/2026-06-03-djangoql-derived-fields-design.md`

This is NEW content documenting the feature shipped in the previous plan. Read `djangoql/extras.py` and the spec to ensure accuracy.

- [ ] **Step 1: Read the implementation**

Read `djangoql/extras.py` (classes `DatePartField`, `DateExtractField`, `TimeExtractField`, `DatePartsSchemaMixin`, `AggregateField`, `CountField`, `NumericAggregateField`, `SumField`/`AvgField`/`MinField`/`MaxField`, `AggregateSchemaMixin`, `ExtrasSchema`) and the spec's Components 1–3.

- [ ] **Step 2: Write `docs/derived-fields.md`**

Cover, accurately and with runnable examples:
- **Enabling**: `from djangoql.extras import ExtrasSchema` and set `djangoql_schema = ExtrasSchema` on the admin (or compose `DatePartsSchemaMixin` / `AggregateSchemaMixin` into a custom schema). Note it is opt-in and the default schema is unchanged.
- **Date/time parts** table: `DateField` → `year, month, day, week_day, quarter, week, iso_year, iso_week_day`; `DateTimeField` → those + `hour, minute, second` + `date` + `time`; `TimeField` → `hour, minute, second`. Examples: `written__year >= 2020`, `written__month in (6, 7, 8)`, `written__hour < 9`, `written__date = "2020-01-01"`, `written__time >= "09:00"`.
- **`week_day` gotcha**: Django returns `1=Sunday … 7=Saturday`; `iso_week_day` returns `1=Monday … 7=Sunday`. Use an admonition (`!!! note`).
- **Relation aggregates**: `<rel>__count` (counts to-many relations; matches `= 0` for empty via Coalesce) and `<rel>__<numeric_field>__{sum,avg,min,max}`. Examples: `book__count > 5`, `book__price__avg > 30`, nested `author.book__count > 1`. Explain they are correlated subqueries applied lazily (only when referenced) and work in both admin and queryset API.
- **Which relations/fields**: all to-many (reverse FK + M2M, both directions); numeric fields excluding PK, FK ids, and non-editable columns; relations with a hidden reverse (`related_name='+'`) are skipped.
- **Precision note** (admonition): numeric aggregates use a float output field for v1; very large `Sum` over `DecimalField` may lose sub-unit precision.
- **`suggested` flag**: `DjangoQLField(suggested=False)` hides a field from autocomplete while keeping it usable in queries; distinct from `suggest_options` (which controls value suggestions). Default is `True`.
- A short "Recipes" section, e.g. find users with no books (`book__count = 0`), summer posts (`written__month in (6, 7, 8)`).

- [ ] **Step 3: Verify the page builds (still non-strict)**

Run: `uv run mkdocs build -d /tmp/mkdocs_site_t3 2>&1 | tail -20`
Expected: builds with no remaining warnings about missing nav pages. Confirm: `test -e /tmp/mkdocs_site_t3/derived-fields/index.html && echo OK`.

- [ ] **Step 4: Commit**

```bash
git add docs/derived-fields.md
git commit -m "docs: add Derived fields page (date/time parts, aggregates, suggested flag)"
```

---

## Task 4: Trim README, cross-link, strict build

**Files:**
- Modify: `README.md`
- Verify: whole site

- [ ] **Step 1: Trim `README.md` to an overview**

Reduce `README.md` to: the title, the existing PyPI/CI badges, the screenshot, a 2–4 sentence description, the existing PyPI package-name vs import-name note, a short Features list (keep), Installation quickstart (keep the pip line), and a prominent link to the documentation site / `docs/` (e.g. "Full documentation: see the `docs/` directory or the rendered site."). Remove the long sections now living in `docs/` (admin setup, language reference, schema, custom fields, queryset, completion widget, i18n) and the old `## Contents` TOC. Keep `## Supported by` and `## License` or move them to a one-line mention — your choice, but do not lose the license reference.

Do NOT remove the PyPI badges or the package-name note (they matter for the published package page).

- [ ] **Step 2: Strict build of the whole site**

Run: `uv run mkdocs build --strict -d /tmp/mkdocs_site_final 2>&1 | tail -30`
Expected: completes with NO warnings (strict turns warnings into errors). Fix any broken internal links, missing nav entries, or orphaned pages until strict passes.

- [ ] **Step 3: Confirm exclusion + completeness**

Run:
```
test ! -e /tmp/mkdocs_site_final/superpowers && echo "superpowers excluded OK"
for p in index installation admin language schema derived-fields queryset completion-widget i18n; do test -e /tmp/mkdocs_site_final/$p/index.html && echo "$p OK" || echo "$p MISSING"; done
```
Expected: exclusion OK and all pages `OK`.

- [ ] **Step 4: Run the test suite (sanity — no code changed, but confirm nothing broke)**

Run: `uv run pytest -q`
Expected: all pass (unchanged from the previous plan; this plan touches no application code).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: trim README to overview; point to MkDocs site"
```

---

## Self-Review Notes (author)

- **Spec coverage (Component 4):** MkDocs under `docs/` (Task 1), Material theme (Task 1), `docs/superpowers/` excluded (Task 1, verified Tasks 1/4), English logically-organized migration of all README sections (Task 2 — full mapping table), new derived-fields page incl. `week_day` gotcha, precision caveat, `suggested` flag (Task 3), README trimmed with badges + package-name note retained (Task 4). The spec's "GitHub Pages/RTD deployment" is explicitly out of scope (no deploy task) — consistent with the spec's non-goals.
- **No placeholders:** every task has concrete files, the exact `mkdocs.yml`, the section→page mapping, and exact verify/commit commands. `docs/index.md` placeholder in Task 1 is explicitly overwritten in Task 2.
- **Strict-build sequencing:** `--strict` is only enforced in Task 4 (after all nav pages exist); Tasks 1–3 use non-strict builds plus explicit file-existence checks, because `--strict` fails on not-yet-created nav targets. This is intentional and documented in each task.
- **Risk:** image/asset paths in README may be repo-relative; Task 2 Step 2 instructs keeping absolute URLs and relocating/repointing repo-relative images so strict build resolves them.
