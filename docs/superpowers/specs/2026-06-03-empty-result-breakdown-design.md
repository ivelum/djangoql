# C — "Where the query runs out of data" (empty-result breakdown)

Date: 2026-06-03
Status: Design (not yet approved for implementation).

## Problem

A multi-condition query returns **zero rows**, and the user can't tell *why*.
For a single condition (`doi = "x"`) it's obvious — nothing matches. But for
`doi = "x" and rok in (1,2,3) and ...` the user wants to see **where in the
query the data runs out**: e.g. `doi = "x"` matches 500 rows, adding
`rok in (...)` narrows to 4, and the next `and` drops it to 0 — so *that*
condition is the culprit.

User's explicit scope correction: **not** limited to a flat `AND` chain — it
should work for an arbitrary boolean structure (`and` / `or` / parentheses) and
point at where the result becomes empty.

## AST facts (grounding)

The parser produces a binary tree of `Expression(left, operator, right)`:

- `operator` is either a `Logical` (`and` / `or`) — an internal node combining
  two sub-expressions — or a `Comparison` — a **leaf** (`Name <op> Const/List`).
- There is **no unary not-of-a-subtree**. Negation is folded into comparison
  operators (`!=`, `!~`, `not in`, `not startswith`, `not endswith`), so a leaf
  can be negated but a whole subtree cannot.
- Grouping with parentheses just nests `Expression` nodes.

So the tree is AND/OR over (possibly negated) comparison leaves.

## Approach

Walk the validated AST and compute `count()` of the base queryset filtered by
each **sub-expression**, then annotate the tree and highlight the node(s) where
the count collapses to 0.

Per node:

- **Leaf** (`Comparison`): `count` = rows matching that single condition.
- **`AND` node**: `count(left ∧ right)`. The interesting signal: if this count is
  `0` while `count(left) > 0` **and** `count(right) > 0`, this `and` is a *killer
  intersection* — each side has rows, but they don't overlap. Highlight it.
- **`OR` node**: `count(left ∨ right)`. It is `0` only if both branches are `0`;
  highlight the (zero) branches.

Reuse the existing pipeline to count a subtree: `apply_search`/`build_filter`
operate on an `Expression` node + schema instance, and `collect_annotations`
gathers any derived-field annotations for that node. So for each sub-expression
we can build its `Q` (plus annotations) and run `.count()` on the base queryset.

The result is a tree of `{expr_text, count, role}` where `role` flags leaves,
killer `AND`s, and dead `OR` branches.

## Trigger & cost

- **Lazy / on-demand.** Only compute when the overall result is empty *and* a
  DjangoQL search is active. Optionally behind a click ("explain why empty") so
  the extra queries aren't run on every empty search.
- Cost = one `count()` per evaluated node. Typical queries are small. Guard with
  a configurable **max node budget**; if the AST exceeds it, evaluate only the
  top-level conjuncts and **`log()`/annotate that the breakdown was truncated**
  (no silent cap).

## Rendering

- **Admin changelist empty state**: render the query as its condition tree with
  per-node counts (indented list or simple tree), the killer node highlighted,
  e.g.

  ```
  doi = "x"                       500
  and rok in (1, 2, 3)              4
  and status = "active"             0   ← brak danych od tego warunku
  ```

- **Queryset API**: a helper, e.g. `explain_empty(queryset, search, schema)`,
  returning the structured tree so callers can render it themselves.

## API sketch

```python
# returns a tree of nodes: {text, count, role, children}
breakdown = explain_empty(queryset, search_text, schema=ExtrasSchema)
```

Admin: a mixin/template hook that, when the DjangoQL result is empty, computes
`explain_empty` and renders it in the empty-results area.

## Open questions (resolve in implementation)

- **Which nodes to evaluate** — every node, vs. leaves + immediate combinations
  — to stay informative without exploding the query count. Leaning: every node,
  with the max-node budget as the guard.
- **Leaf labeling** — reconstruct the original source slice per node vs. render
  from the AST. Source slices read best; needs token spans from the parser.
- **OR presentation** — how to show which branches contribute zero without
  visual noise.
- **Performance guard defaults** and whether to gate behind a click by default.
- **Surfacing outside the admin** and **i18n** of the annotations.

## Out of scope (v1)

- Query-rewriting suggestions / "did you mean".
- Counting across `OR` for *positive* contribution attribution beyond
  zero/non-zero (e.g. exact marginal contribution of each branch).
