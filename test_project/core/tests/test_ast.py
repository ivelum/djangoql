from unittest import TestCase

from djangoql.ast import Comparison, Const, Expression, List, Name


class DjangoQLASTTest(TestCase):
    def test_equality(self):
        self.assertEqual(
            Expression(Name('age'), Comparison('='), Const(18)),
            Expression(Name('age'), Comparison('='), Const(18)),
        )
        self.assertNotEqual(
            Expression(Name('age'), Comparison('='), Const(42)),
            Expression(Name('age'), Comparison('='), Const(18)),
        )

    def test_not_equal_across_types(self):
        # __eq__ must short-circuit to False for a different node class
        # rather than raising while comparing attributes.
        self.assertNotEqual(Const(1), Name('age'))
        self.assertNotEqual(Name('age'), Const(1))

    def test_repr(self):
        expr = Expression(Name('age'), Comparison('='), Const(18))
        rendered = repr(expr)
        # __str__/__repr__ are the same callable; both should describe the node.
        self.assertEqual(rendered, str(expr))
        self.assertTrue(rendered.startswith('<Expression:'))
        self.assertIn('operator=', rendered)
        # A node holding a list renders its truthy children joined in brackets.
        self.assertIn('[', repr(List([Const(1), Const(2)])))

    def test_name_accepts_tuple(self):
        # Name normalises list / tuple / scalar inputs to a list of parts.
        self.assertEqual(Name(['a', 'b']).parts, ['a', 'b'])
        self.assertEqual(Name(('a', 'b')).parts, ['a', 'b'])
        self.assertEqual(Name('a').parts, ['a'])
        self.assertEqual(Name(('a', 'b')).value, 'a.b')
