# Object-reference autocomplete (example project) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the DjangoQL search box render suggestions legibly in the admin and demo, then wire the existing `djangoql.extras.AutocompleteField` into `example_project` so `Book.author__rel` is an object-picker (`"John Smith [4290]"` → filter by pk) that coexists with `author.` relation traversal.

**Architecture:** Two prerequisite UI bug fixes (completion→highlight repaint; demo popup styling) followed by example wiring that uses the already-built, already-tested `AutocompleteSchemaMixin`. No new library code.

**Tech Stack:** Django admin, vanilla JS completion widget (webpack bundle from `djangoql-completion`), `highlight.js` overlay, SCSS-free plain CSS in the example.

---

### Task 1: Completion selection fires `input` (fix white-on-white)

**Files:**
- Modify: `completion-widget/index.js` (source of truth — DONE)
- Modify: `djangoql/static/djangoql/js/completion.js` (committed bundle — surgical patch)

- [ ] **Step 1: Confirm `index.js` wraps `selectCompletion`**

`completion-widget/index.js` must contain a wrapper that calls the original `selectCompletion` then dispatches a bubbling `input` event on `this.textarea`. (Already written.)

- [ ] **Step 2: Surgically patch the committed bundle**

In `djangoql/static/djangoql/js/completion.js`, the bundle ends with `…window.DjangoQL=M}()}();`. Replace the `window.DjangoQL=M` assignment with a prototype wrapper that dispatches `input` after `selectCompletion`:

```js
var __dqlSel=M.prototype.selectCompletion;M.prototype.selectCompletion=function(){__dqlSel.apply(this,arguments);if(this.textarea){var e;try{e=new Event("input",{bubbles:true})}catch(t){e=document.createEvent("Event");e.initEvent("input",true,false)}this.textarea.dispatchEvent(e)}};window.DjangoQL=M
```

- [ ] **Step 3: Verify the patch is present and the bundle still parses**

Run: `node -e "require('./djangoql/static/djangoql/js/completion.js'); console.log('parsed ok')"` (expect it to print, or at least not throw a SyntaxError; the file assigns `window` so a ReferenceError on `window` is fine — a SyntaxError is not).
Alternative: `node --check djangoql/static/djangoql/js/completion.js` → Expected: no output (syntax OK).

- [ ] **Step 4: Commit**

```bash
git add completion-widget/index.js djangoql/static/djangoql/js/completion.js
git commit -m "fix(completion): dispatch input on selection so highlight overlay repaints"
```

---

### Task 2: Style the demo completion popup for the dark theme

**Files:**
- Modify: `example_project/library/templates/library/base.html` (CSS load order)
- Modify: `example_project/library/templates/library/demo.html` (remove the now-moved link; update hint)
- Modify: `example_project/library/static/library/css/demo.css` (popup styling)

- [ ] **Step 1: Load `completion.css` before `demo.css`**

In `base.html`, add `<link rel="stylesheet" href="{% static 'djangoql/css/completion.css' %}">` immediately after the `highlight.css` link (so `demo.css`, loaded next, overrides it). In `demo.html`'s `{% block head %}`, remove the `completion.css` link (now in base).

- [ ] **Step 2: Add dark-theme popup styling to `demo.css`**

Append:

```css
/* Restyle the completion popup for this dark theme (its defaults target the
   light admin: white box, no text colour -> our light --ink text is invisible). */
.djangoql-completion {
  margin-top: 6px;
  background: var(--panel-2);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  box-shadow: 0 18px 50px -20px rgba(0, 0, 0, 0.85);
  overflow: hidden;
  z-index: 50;
}
.djangoql-completion ul { max-height: 280px; }
.djangoql-completion li { color: var(--ink); padding: 6px 12px; }
.djangoql-completion li:hover { background: rgba(124, 92, 255, 0.18); color: var(--ink); }
.djangoql-completion .active { background: var(--accent); color: #fff; }
.djangoql-completion li i { color: var(--muted); }
.djangoql-completion .syntax-help { border-top-color: rgba(255, 255, 255, 0.12); }
```

- [ ] **Step 3: Update the demo hint (in `demo.html`)**

Replace the hint `<p class="hint">` body so it explains: relations use **dots** (`author.country.name`), and `author__rel` is an object-picker that suggests real authors as `"Name [id]"`.

- [ ] **Step 4: Verify rendered page links CSS in the right order**

Run: `cd example_project && ../.venv/bin/python manage.py check` → Expected: `System check identified no issues`.
(Visual confirmation happens in Task 4.)

- [ ] **Step 5: Commit**

```bash
git add example_project/library/templates/library/base.html example_project/library/templates/library/demo.html example_project/library/static/library/css/demo.css
git commit -m "feat(example): legible dark-theme completion popup + dot-syntax hint"
```

---

### Task 3: Wire `AutocompleteField` into the example (`author__rel` picker)

**Files:**
- Create: `example_project/library/schema.py`
- Modify: `example_project/library/admin.py`
- Modify: `example_project/library/views.py`

- [ ] **Step 1: Create `example_project/library/schema.py`**

```python
"""Showcase schema: expose Book.author both as a relation (dot-traversal) and
as an object-picker (author__rel) using djangoql's AutocompleteField."""
from djangoql.extras import AutocompleteSchemaMixin
from djangoql.schema import DjangoQLSchema

from .models import Author, Book


class BookSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    autocomplete = {
        Book: {
            'author__rel': {
                'lookup_name': 'author',  # filter the real FK column by pk
                'queryset': lambda s: Author.objects.filter(
                    name__icontains=s,
                ).order_by('name'),
                'search_fields': ['name'],
                'label': str,
            },
        },
    }

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        if model is Book:
            fields.append('author__rel')
        return fields
```

- [ ] **Step 2: Point the admin at the schema**

In `example_project/library/admin.py`, add `from .schema import BookSchema` and set `djangoql_schema = BookSchema` on `BookAdmin`.

- [ ] **Step 3: Use the schema in the demo views**

In `example_project/library/views.py`: import `from .schema import BookSchema`; in `index()` serialize `BookSchema(Book)` instead of `DjangoQLSchema(Book)`; in `api_search` (and `api_explain` if it parses) pass `schema=BookSchema` to `apply_search`/`explain` where they accept it.

- [ ] **Step 4: Smoke-test the schema in a shell**

Run:
```bash
cd example_project && ../.venv/bin/python -c "
import django,os,sys; sys.path.insert(0,'.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','example_project.settings'); django.setup()
from library.schema import BookSchema
from library.models import Book
from djangoql.serializers import DjangoQLSchemaSerializer
d=DjangoQLSchemaSerializer().serialize(BookSchema(Book))
f=d['models']['library.book']['author__rel']
print('author__rel:', f['type'], 'options sample:', (f['options'] or [])[:2])
print('author still relation:', d['models']['library.book']['author'].get('relation'))
"
```
Expected: `author__rel: str options sample: ['<Name> [<id>]', …]` and `author still relation: library.author`.

- [ ] **Step 5: Confirm the library test suite is still green (nothing regressed)**

Run: `.venv/bin/python -m pytest test_project/core/tests/test_autocomplete.py -q` → Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add example_project/library/schema.py example_project/library/admin.py example_project/library/views.py
git commit -m "feat(example): register author__rel object-picker via AutocompleteSchemaMixin"
```

---

### Task 4: Browser verification (admin + demo)

**Files:** none (manual/scripted verification)

- [ ] **Step 1: Run the example server**

Run: `cd example_project && ../.venv/bin/python manage.py runserver` (background).

- [ ] **Step 2: Admin check — white-on-white fixed**

In `/admin/library/book/`: type `author`, pick `country` from the popup. Expected: the inserted `.country` is now visible and coloured (not white-on-white). Pick a value suggestion (e.g. `None`) — also visible.

- [ ] **Step 3: Demo check — legible popup + picker**

On `/`: confirm the popup is dark-themed and readable. Type `author__rel = ` → popup lists `"<name> [<id>]"`. Pick one, run → results filter to that author's books. Confirm `author.country.name = "..."` (dot traversal) still works.

- [ ] **Step 4: Confirm typing highlights**

Type a query with a string/number/operator; confirm syntax colours render (overlay) in both admin and demo.

---

## Self-review

- **Spec coverage:** prerequisite fix 1 → Task 1; fix 2 + hint → Task 2; wiring → Task 3; manual verification → Task 4. All covered.
- **Placeholder scan:** none.
- **Consistency:** `BookSchema` name, `author__rel`, `lookup_name='author'` consistent across tasks and spec.
