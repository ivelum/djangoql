"""Render a DjangoQL AST back to text.

Two renderers, both driven purely by the parsed AST (no database, no schema):

- :func:`serialize_node` — a compact, single-line canonical form. Logical
  children are parenthesised, leaves are not. This is the shared building block
  for any "reconstruct the query / a sub-expression from the AST" need (the
  empty-result breakdown reuses it for its node labels).
- :func:`format_query` — a multi-line pretty-printer with indentation, for
  turning a long flat query into a readable, nested layout.

The parser drops redundant parentheses (``(a)`` parses to ``a``) and represents
logical expressions as a binary tree respecting operator precedence and explicit
grouping. Both renderers add back the parentheses required so that re-parsing
the rendered text yields an **equal** AST — round-trip safety is covered by the
tests.
"""

from .ast import Logical
from .parser import DjangoQLParser


__all__ = ['format_query', 'serialize_node']


def _quote(value):
    if isinstance(value, str):
        return '"%s"' % value
    if value is None:
        return 'None'
    if isinstance(value, bool):
        return 'True' if value else 'False'
    return str(value)


def _is_logical(node):
    return isinstance(node.operator, Logical)


def _leaf(node):
    """Render a single comparison leaf (``name op value``)."""
    name = node.left.value
    op = node.operator.operator
    right = node.right
    # A List right-hand side (``in (1, 2)``) renders its items.
    if hasattr(right, 'items'):
        values = ', '.join(_quote(v) for v in right.value)
        return f'{name} {op} ({values})'
    return f'{name} {op} {_quote(right.value)}'


def serialize_node(node):
    """Compact, single-line canonical rendering of an AST node.

    Leaves render as ``name op value``; a logical node renders its operands
    joined by the operator, parenthesising any operand that is itself logical
    so the result re-parses to an equal AST.
    """
    if not _is_logical(node):
        return _leaf(node)
    return '{} {} {}'.format(
        _side(node.left),
        node.operator.operator,
        _side(node.right),
    )


def _side(node):
    text = serialize_node(node)
    return '(%s)' % text if _is_logical(node) else text


def _flatten(node, op):
    """Flatten a chain of the *same* logical operator into a flat operand list.

    ``a and b and c`` becomes ``[a, b, c]``. Operands joined by a different
    operator are returned whole (and later parenthesised).
    """
    if _is_logical(node) and node.operator.operator == op:
        return _flatten(node.left, op) + _flatten(node.right, op)
    return [node]


def _format_lines(node, level, unit):
    """Return the pretty-printed lines for ``node`` at indentation ``level``.

    A logical group prints its first operand at ``level`` and each following
    operand on its own ``op …`` line indented one ``unit`` deeper. An operand
    that is itself logical is wrapped in parentheses and laid out as a block.
    """
    if not _is_logical(node):
        return [unit * level + _leaf(node)]

    op = node.operator.operator
    operands = _flatten(node, op)
    lines = []
    for index, operand in enumerate(operands):
        if index == 0:
            lines += _operand_lines(operand, level, '', unit)
        else:
            lines += _operand_lines(operand, level + 1, op + ' ', unit)
    return lines


def _operand_lines(operand, level, prefix, unit):
    pad = unit * level
    if not _is_logical(operand):
        return [pad + prefix + _leaf(operand)]
    # A nested logical operand becomes a parenthesised block.
    inner = _format_lines(operand, level + 1, unit)
    return [pad + prefix + '('] + inner + [pad + ')']


def format_query(query, indent=2):
    """Pretty-print a DjangoQL ``query`` string as indented, multi-line text.

    :param query: the DjangoQL search string.
    :param indent: number of spaces per indentation level (default ``2``).
    :return: the formatted query. Re-parsing it yields an AST equal to the
        original, and formatting is idempotent.
    :raises djangoql.exceptions.DjangoQLParserError: when ``query`` is invalid.
    """
    ast = DjangoQLParser().parse(query)
    return '\n'.join(_format_lines(ast, 0, ' ' * indent))
