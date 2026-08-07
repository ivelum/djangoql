# Multi-line queries (Shift+Enter)

DjangoQL queries are whitespace-insensitive, so a query can span several lines:

```
author.name = "Stanisław Lem"
  and written >= 1960
  and (genre = "scifi" or genre = "novel")
```

The completion widget, however, binds **Enter** to *submit* the search. That is
the right default — you usually want to run the query as soon as it is typed —
but it leaves no obvious way to insert a newline.

`multiline.js` fixes that:

| Key           | Action                              |
| ------------- | ----------------------------------- |
| **Enter**     | Submit the query (unchanged)        |
| **Shift+Enter** | Insert a newline at the caret      |

## In the Django admin

Nothing to do. `DjangoQLSearchMixin` already loads `multiline.js` next to the
completion widget, so Shift+Enter works in the admin search box out of the box.

## Outside the admin (your own front-end)

`multiline.js` is a small, framework-agnostic library primitive. It imposes no
styling and no editor — it only turns Shift+Enter into a newline. **How a
multi-line query box looks and behaves beyond that is your decision.**

Load the script and mark your textarea with one of the recognised hooks:

```html
<textarea class="djangoql" name="search"></textarea>
<script src="{% static 'djangoql/js/multiline.js' %}"></script>
```

Recognised automatically: `textarea[name="q"]` (the admin box),
`textarea.djangoql`, and `textarea[data-djangoql]`. To opt a specific element in
explicitly:

```js
DjangoQLMultiline.enable(document.getElementById('my-query-box'));
```

Or change which elements are matched:

```js
DjangoQLMultiline.selector = 'textarea.my-query';
```

## How it works

The script attaches a single **capture-phase** `keydown` listener on `document`.
Capture runs before the widget's own (bubble-phase) handler, so on Shift+Enter
it inserts a newline and calls `stopImmediatePropagation()` — the widget never
sees the event and therefore never submits. Plain Enter is left untouched and
falls through to the widget. Because the listener lives on `document`, it does
not matter when or how the target textarea was created.

See also: [Pretty-print / formatting](pretty-print.md) to auto-indent a
multi-line query.
