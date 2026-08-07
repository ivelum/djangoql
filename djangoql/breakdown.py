"""Explain *why* a DjangoQL query returns zero rows.

When a multi-condition query matches nothing, this module walks the validated
AST and counts the base queryset filtered by each sub-expression, then points
at the node(s) where the result collapses to zero:

- a leaf (single comparison) reports how many rows match it on its own;
- an ``AND`` whose two sides are each non-empty but whose intersection is zero
  is flagged as a *killer intersection* (``role == 'killer_and'``); an ``AND``
  that drops to zero because one side is already zero is still flagged
  ``killer_and`` (it is where the data runs out);
- an ``OR`` is zero only when *both* branches are zero — those branches are
  flagged ``dead_or_branch``; a zero branch of an otherwise non-empty ``OR`` is
  likewise flagged ``dead_or_branch`` so the user sees the part that never
  contributes.

The whole thing is lazy: :func:`explain_empty` returns ``None`` unless there is
an active search *and* the overall result is empty. A configurable
``max_nodes`` budget guards the (one ``count()`` per node) cost; an AST larger
than the budget is evaluated only down to its top-level conjuncts and the
returned tree carries ``truncated=True`` (no silent cap).
"""

from .ast import Logical
from .formatter import serialize_node
from .parser import DjangoQLParser
from .queryset import build_filter
from .schema import DjangoQLSchema


__all__ = ['explain', 'explain_empty']

# Default cost guard: how many AST nodes we are willing to count() before
# truncating the breakdown to the top-level conjuncts.
DEFAULT_MAX_NODES = 50

# Node labels are rendered from the AST (the parser exposes no per-node source
# spans). ``serialize_node`` gives a stable, unambiguous one-line rendering and
# is shared with the pretty-printer.
_leaf_text = serialize_node
_node_text = serialize_node


def _count(base, node, schema_instance):
    """count() of the base queryset filtered by a single sub-expression.

    Annotations required by the sub-expression (e.g. for an aggregate/derived
    field referenced inside it) are collected and applied before filtering, so
    counting a subtree mirrors :func:`djangoql.queryset.apply_search`.
    """
    annotations = schema_instance.collect_annotations(node)
    qs = base.annotate(**annotations) if annotations else base
    return qs.filter(build_filter(node, schema_instance)).count()


class _Budget:
    """A mutable node budget shared across the recursive build.

    Each counted node consumes one unit. Once the budget is exhausted the
    build stops descending and records that the breakdown was truncated.
    """

    def __init__(self, limit):
        self.remaining = limit
        self.truncated = False

    def take(self):
        if self.remaining <= 0:
            self.truncated = True
            return False
        self.remaining -= 1
        return True


def _build(node, base, schema_instance, budget):
    """Recursively build a breakdown node dict for an Expression.

    Descends only while the shared node ``budget`` allows; when it is exhausted
    the current conjunct is still counted but its internals are not, and the
    budget records the truncation.
    """
    count = _count(base, node, schema_instance)

    if not isinstance(node.operator, Logical):
        return {
            'text': _leaf_text(node),
            'count': count,
            'role': 'leaf',
            'children': [],
        }

    op = node.operator.operator

    if not budget.take():
        # Budget exhausted: report this conjunct's count but stop descending.
        return {
            'text': _node_text(node),
            'count': count,
            'role': op,
            'children': [],
            'truncated': True,
        }

    left = _build(node.left, base, schema_instance, budget)
    right = _build(node.right, base, schema_instance, budget)

    role = op
    if op == 'and':
        # The AND is where the data runs out: it collapses to zero.
        if count == 0:
            role = 'killer_and'
    else:  # or
        # Flag any zero branch as dead; if both are dead the OR itself is zero.
        for branch in (left, right):
            if branch['count'] == 0:
                branch['role'] = 'dead_or_branch'

    return {
        'text': _node_text(node),
        'count': count,
        'role': role,
        'children': [left, right],
    }


def _parse_and_validate(queryset, search, schema):
    """Parse and schema-validate ``search``; return ``(ast, schema_instance)``.

    Returns ``None`` when there is no active search. Parser/schema errors
    propagate to the caller.
    """
    if not search or not search.strip():
        return None
    schema = schema or DjangoQLSchema
    schema_instance = schema(queryset.model)
    ast = DjangoQLParser().parse(search)
    schema_instance.validate(ast)
    return ast, schema_instance


def _build_tree(queryset, ast, schema_instance, max_nodes):
    budget = _Budget(max_nodes)
    tree = _build(ast, queryset, schema_instance, budget)
    if budget.truncated:
        tree['truncated'] = True
    return tree


def explain(queryset, search, schema=None, *, max_nodes=DEFAULT_MAX_NODES):
    """Break ``search`` down into a per-node count tree against ``queryset``.

    Unlike :func:`explain_empty`, this *always* builds the tree (one
    ``count()`` per node) regardless of whether the overall result is empty, so
    it is the primitive behind an on-demand "explain"/"show counts" action. It
    is therefore caller-triggered, never run implicitly per search.

    :param queryset: the *base* (unfiltered) queryset the search runs against.
    :param search: the DjangoQL search string.
    :param schema: optional :class:`~djangoql.schema.DjangoQLSchema` subclass.
    :param max_nodes: cost guard — if the AST has more nodes than this, only
        the top-level conjuncts are counted and the returned tree carries
        ``truncated=True``.
    :return: a breakdown tree of ``{text, count, role, children}`` (plus an
        optional ``truncated`` flag), or ``None`` when there is no active
        search.
    """
    prepared = _parse_and_validate(queryset, search, schema)
    if prepared is None:
        return None
    ast, schema_instance = prepared
    return _build_tree(queryset, ast, schema_instance, max_nodes)


def explain_empty(
    queryset, search, schema=None, *, max_nodes=DEFAULT_MAX_NODES
):
    """Explain why ``search`` returns zero rows against ``queryset``.

    Like :func:`explain`, but lazy: it runs a single ``count()`` first and
    returns ``None`` unless the overall result is empty, so the per-node
    counting only happens for the zero-rows case. This is what the admin uses
    implicitly after a search.

    :param queryset: the *base* (unfiltered) queryset the search runs against.
    :param search: the DjangoQL search string.
    :param schema: optional :class:`~djangoql.schema.DjangoQLSchema` subclass.
    :param max_nodes: cost guard — if the AST has more nodes than this, only
        the top-level conjuncts are counted and the returned tree carries
        ``truncated=True``.
    :return: a breakdown tree of ``{text, count, role, children}`` (plus an
        optional ``truncated`` flag on the root), or ``None`` when there is no
        active search or the overall result is *not* empty (the breakdown only
        applies to the zero-rows case).
    """
    prepared = _parse_and_validate(queryset, search, schema)
    if prepared is None:
        return None
    ast, schema_instance = prepared

    # Lazy trigger: only explain when the overall result is actually empty.
    total = _count(queryset, ast, schema_instance)
    if total != 0:
        return None

    return _build_tree(queryset, ast, schema_instance, max_nodes)
