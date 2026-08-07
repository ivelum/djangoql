# DjangoQL — Query UX example project

A small, self-contained Django project that demonstrates the query-UX features
of DjangoQL on a realistic, richly related dataset (books → authors →
countries, publishers, and genres):

- **Multi-line queries** — `Shift+Enter` inserts a newline, `Enter` runs.
- **Pretty-print / formatting** — a *Format* button reflows a query with
  indentation.
- **Per-branch record counts** — an *Explain counts* button shows how many rows
  each sub-expression matches and where an `AND` collapses to zero.
- **Syntax highlighting** — the library's restyled lightweight overlay.
- **Auto-completion** — field and value names complete as you type (the
  DjangoQL completion widget), on the demo page and in the admin.
- The **Django admin** with the completion widget, multi-line input, and the
  (opt-in) highlighting overlay turned on.

> The colours and layout here are this demo's own choices. DjangoQL ships the
> primitives (completion widget, tokenizer, overlay, `format`/`explain`
> endpoints, `multiline.js`); it imposes none of the styling.

## What it looks like

Running a query — auto-completion, live syntax highlighting, results:

![Search demo](../docs/img/demo-search.png)

The **Format** button re-indents a query:

![Formatted query](../docs/img/demo-format.png)

**Explain counts** shows per-branch row counts — here each side matches ~500
rows but their `and` matches none, so the red node is where the data runs out:

![Per-branch counts for an empty result](../docs/img/demo-explain.png)

Syntax errors are pinpointed in the query box:

![Syntax error highlighted](../docs/img/demo-error.png)

## Requirements

- Python 3.9+ and Django (already pulled in as a dependency of this repo).
- The repository checked out; run the commands below from `example_project/`.
- Everything works fully offline.

## Run it

From the repository root, the project uses `uv` (see the top-level README). If
you have your own virtualenv with `django` + this `djangoql` package installed,
drop the `uv run` prefix.

```bash
cd example_project

# 1. Create the database schema
uv run python manage.py migrate

# 2. Fill it with lots of related demo data (~3000 books by default)
uv run python manage.py seed_demo
#    more data:           uv run python manage.py seed_demo --books 8000
#    wipe & reseed:       uv run python manage.py seed_demo --flush

# 3. (optional) a superuser, to log into the admin
uv run python manage.py createsuperuser

# 4. Start the server
uv run python manage.py runserver
```

Then open:

| URL                         | What it shows                                            |
| --------------------------- | ------------------------------------------------------- |
| <http://127.0.0.1:8000/>       | Search demo: auto-completion, multi-line, highlight, Format, Explain counts, results |
| <http://127.0.0.1:8000/syntax-help/> | The DjangoQL syntax help rendered as **HTML from Markdown**, with a language switcher (`?lang=pl`, `?lang=ja`, …) |
| <http://127.0.0.1:8000/admin/> | Django admin (completion + multi-line + highlight overlay; the in-admin syntax help is also HTML here) |

### Markdown help

djangoql authors its syntax help as per-language Markdown and renders it to HTML
**only when a Markdown compiler is importable** — otherwise it shows the raw
Markdown in a `<pre>` block. The library itself does not depend on one. This
example lists `markdown` in `requirements.txt`, so both the standalone
`/syntax-help/` page and the admin help page render as HTML. Install the example
deps with `pip install -r requirements.txt` (or rely on the repo's dev
environment, where `markdown` is already present).

## Things to try

In the search box on the home page (or the admin Book search):

```
rating > 4.5 and in_stock = True
author.country.name = "Poland" or publisher.name ~ "Press"
year >= 2000 and (genres.name = "Science Fiction" or rating > 4)
```

- Start typing a field name (e.g. `author.`) and pick from the
  **auto-completion** suggestions.
- Press **Shift+Enter** to break a long query across lines, then **Format** to
  re-indent it.
- Click **Explain counts** to see per-branch row counts — try a query whose two
  halves each match many rows but whose combination matches few; the collapsing
  `AND` is highlighted.

## How it is wired (for reference)

- `library/models.py` — the related schema (`Book.author`, `Book.publisher`,
  `Book.genres`, `Author.country`, …).
- `library/management/commands/seed_demo.py` — reproducible data generator.
- `library/admin.py` — `DjangoQLSearchMixin` with `djangoql_highlight = True`.
- `library/views.py` — standalone pages and the `api/format`, `api/explain`,
  `api/search` endpoints that call the DjangoQL primitives directly.
- `library/static/library/` + `templates/library/` — the demo's own styling and
  glue (this is the "go wild" part).

The API endpoints are `csrf_exempt` to keep the demo simple — do not copy that
into production.
