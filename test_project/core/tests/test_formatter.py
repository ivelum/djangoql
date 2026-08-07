"""Tests for djangoql.formatter — canonical one-line serialization and the
multi-line pretty-printer.

These are pure AST/string tests: no database and no schema validation are
involved, so they run fast and in isolation.
"""

from djangoql.formatter import format_query, serialize_node
from djangoql.parser import DjangoQLParser


def _parse(query):
    return DjangoQLParser().parse(query)


class TestSerializeNode:
    """serialize_node: compact, single-line, canonical rendering of an AST.

    Logical children are parenthesised; leaves are not.
    """

    def test_leaf_equality(self):
        assert serialize_node(_parse('genre = 1')) == 'genre = 1'

    def test_leaf_string_is_quoted(self):
        assert serialize_node(_parse('name = "x"')) == 'name = "x"'

    def test_leaf_none_and_bool(self):
        assert serialize_node(_parse('a = None')) == 'a = None'
        assert serialize_node(_parse('a = True')) == 'a = True'
        assert serialize_node(_parse('a = False')) == 'a = False'

    def test_leaf_in_list(self):
        assert serialize_node(_parse('a in (1, 2, 3)')) == 'a in (1, 2, 3)'

    def test_dotted_name(self):
        assert (
            serialize_node(_parse('author.name = "x"')) == 'author.name = "x"'
        )

    def test_flat_and_chain_has_no_redundant_outer_parens(self):
        # Right-associative AST: a and (b and c). serialize parenthesises the
        # logical right child but not leaves.
        assert serialize_node(_parse('a = 1 and b = 2')) == 'a = 1 and b = 2'

    def test_nested_logical_child_is_parenthesised(self):
        assert (
            serialize_node(_parse('a = 1 or (b = 2 and c = 3)'))
            == 'a = 1 or (b = 2 and c = 3)'
        )

    def test_left_logical_child_is_parenthesised(self):
        assert (
            serialize_node(_parse('(a = 1 and b = 2) or c = 3'))
            == '(a = 1 and b = 2) or c = 3'
        )

    def test_roundtrips_to_equal_ast(self):
        for query in [
            'genre = 1',
            'a = 1 and b = 2 and c = 3',
            'a = 1 or (b = 2 and c = 3)',
            '(a = 1 and b = 2) or c = 3',
            'a in (1, 2) and b ~ "x"',
        ]:
            assert _parse(serialize_node(_parse(query))) == _parse(query)


class TestFormatQuery:
    """format_query: multi-line, indented rendering."""

    def test_single_leaf_unchanged(self):
        assert format_query('genre = 1') == 'genre = 1'

    def test_two_term_and(self):
        assert format_query('a = 1 and b = 2') == 'a = 1\n  and b = 2'

    def test_three_term_and(self):
        assert (
            format_query('a = 1 and b = 2 and c = 3')
            == 'a = 1\n  and b = 2\n  and c = 3'
        )

    def test_or_with_nested_and_block(self):
        assert format_query('a = 1 or (b = 2 and c = 3)') == (
            'a = 1\n  or (\n    b = 2\n      and c = 3\n  )'
        )

    def test_leading_block_then_continuation(self):
        assert format_query('(a = 1 and b = 2) or c = 3') == (
            '(\n  a = 1\n    and b = 2\n)\n  or c = 3'
        )

    def test_custom_indent_width(self):
        assert (
            format_query('a = 1 and b = 2', indent=4) == 'a = 1\n    and b = 2'
        )

    def test_in_list_leaf(self):
        assert format_query('a in (1, 2, 3)') == 'a in (1, 2, 3)'

    def test_roundtrips_to_equal_ast(self):
        for query in [
            'genre = 1',
            'a = 1 and b = 2 and c = 3',
            'a = 1 or (b = 2 and c = 3)',
            '(a = 1 and b = 2) or c = 3',
            'a in (1, 2) and (b ~ "x" or c = None)',
        ]:
            assert _parse(format_query(query)) == _parse(query)

    def test_idempotent(self):
        for query in [
            'a = 1 and b = 2 and c = 3',
            'a = 1 or (b = 2 and c = 3)',
            '(a = 1 and b = 2) or c = 3',
        ]:
            once = format_query(query)
            assert format_query(once) == once
