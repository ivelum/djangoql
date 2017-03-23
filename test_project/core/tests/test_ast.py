from unittest import TestCase

from djangoql.ast import Expression, Name, Comparison, Const


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
