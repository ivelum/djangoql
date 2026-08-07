# Pretty-print / formatting

A long flat query is hard to read:

```
author.name = "Lem" and written >= 1960 and (genre = "scifi" or genre = "novel")
```

DjangoQL can re-render it as indented, multi-line text:

```
author.name = "Lem"
  and written >= 1960
  and (
    genre = "scifi"
      or genre = "novel"
  )
```

This is a pure, AST-driven transformation: the query is parsed and rendered
back. Re-parsing the formatted text yields an **equal** AST, and formatting is
idempotent (formatting an already-formatted query changes nothing).

![Formatted query in the example project](img/demo-format.png)

## Library primitive: `format_query`

```python
from djangoql.formatter import format_query

format_query('a = 1 and b = 2')
# 'a = 1\n  and b = 2'

format_query('a = 1 and b = 2', indent=4)   # spaces per level (default 2)
# 'a = 1\n    and b = 2'
```

`format_query` needs no database and no schema — it only parses. A query that
does not parse raises `djangoql.exceptions.DjangoQLParserError`.

There is also `serialize_node(node)` for the compact, single-line canonical
form of an AST node (logical children parenthesised, leaves not). The
empty-result breakdown reuses it for its node labels.

```python
from djangoql.formatter import serialize_node
from djangoql.parser import DjangoQLParser

serialize_node(DjangoQLParser().parse('(a = 1 and b = 2) or c = 3'))
# '(a = 1 and b = 2) or c = 3'
```

## Admin endpoint

`DjangoQLSearchMixin` exposes a `…/format/` endpoint (URL name
`<app>_<model>_djangoql_format`). It accepts the raw query as `q` (GET or POST)
and returns JSON:

```json
{ "formatted": "a = 1\n  and b = 2" }
```

An unparseable query returns `{"error": "..."}` with HTTP 400. This is the
primitive a front-end "Format" button calls when it has no JavaScript parser of
its own.

!!! note "Wiring the button is your decision"
    The library ships the endpoint, not a button. Whether to add a "Format"
    control, where to place it, and how it looks is the integrator's choice. See
    the `example_project/` for one reference implementation (a Format button next
    to a multi-line query box).

## How parentheses are handled

The parser drops redundant parentheses (`(a)` parses to `a`) and stores
`and`/`or` as a right-associative tree, so source parentheses are not preserved
verbatim. The formatter adds back exactly the parentheses needed to keep the
meaning — a nested logical group of a different operator is wrapped and laid out
as an indented block. Same-operator chains (`a and b and c`) are flattened to a
flat list of lines.

See also: [Multi-line queries](multiline-queries.md) (Shift+Enter to type the
newlines a formatted query contains).
