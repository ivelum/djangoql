from unittest import TestCase

from djangoql.ast import Expression, Name, Comparison, Logical, Const, List
from djangoql.exceptions import DjangoQLParserError
from djangoql.parser import DjangoQLParser


class DjangoQLParseTest(TestCase):
    parser = DjangoQLParser()

    def test_comparisons(self):
        self.assertEqual(
            Expression(Name('age'), Comparison('>='), Const(18)),
            self.parser.parse('age >= 18')
        )
        self.assertEqual(
            Expression(Name('gender'), Comparison('='), Const("female")),
            self.parser.parse('gender = "female"')
        )
        self.assertEqual(
            Expression(Name('name'), Comparison('!='), Const('Gennady')),
            self.parser.parse('name != "Gennady"')
        )
        self.assertEqual(
            Expression(Name('married'), Comparison('in'),
                       List([Const(True), Const(False)])),
            self.parser.parse('married in (True, False)')
        )
        self.assertEqual(
            Expression(Name('smile'), Comparison('!='), Const(None)),
            self.parser.parse('(smile != None)')
        )
        self.assertEqual(
            Expression(Name(['job', 'best', 'title']), Comparison('>'),
                       Const('none')),
            self.parser.parse('job.best.title > "none"')
        )

    def test_escaped_chars(self):
        self.assertEqual(
            Expression(Name('name'), Comparison('~'),
                       Const('Contains a "quoted" string')),
            self.parser.parse('name ~ "Contains a \\"quoted\\" string"')
        )

    def test_logical(self):
        self.assertEqual(
            Expression(
                Expression(Name('age'), Comparison('>='), Const(18)),
                Logical('and'),
                Expression(Name('age'), Comparison('<='), Const(45)),
            ),
            self.parser.parse('age >= 18 and age <= 45')
        )
        self.assertEqual(
            Expression(
                Expression(
                    Expression(Name('city'), Comparison('='), Const('Ivanovo')),
                    Logical('and'),
                    Expression(Name('age'), Comparison('<='), Const(35)),
                ),
                Logical('or'),
                Expression(
                    Expression(Name('city'), Comparison('='), Const('Paris')),
                    Logical('and'),
                    Expression(Name('age'), Comparison('<='), Const(45)),
                ),
            ),
            self.parser.parse('(city = "Ivanovo" and age <= 35) or '
                              '(city = "Paris" and age <= 45)')
        )

    def test_invalid_comparison(self):
        for expr in ('foo > None', 'b <= True', 'c in False', '1 = 1', 'a > b'):
            self.assertRaises(DjangoQLParserError, self.parser.parse, expr)
