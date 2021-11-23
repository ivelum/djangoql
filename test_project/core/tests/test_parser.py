# -*- coding: utf-8 -*-
import unittest.util
from unittest import TestCase

from djangoql.ast import Comparison, Const, Expression, List, Logical, Name
from djangoql.exceptions import DjangoQLParserError
from djangoql.parser import DjangoQLParser


# Show full contents in assertions when comparing long text strings
unittest.util._MAX_LENGTH = 2000


class DjangoQLParseTest(TestCase):
    parser = DjangoQLParser()

    def test_comparisons(self):
        self.assertEqual(
            Expression(Name('age'), Comparison('>='), Const(18)),
            self.parser.parse('age >= 18'),
        )
        self.assertEqual(
            Expression(Name('gender'), Comparison('='), Const('female')),
            self.parser.parse('gender = "female"'),
        )
        self.assertEqual(
            Expression(Name('name'), Comparison('!='), Const('Gennady')),
            self.parser.parse('name != "Gennady"'),
        )
        self.assertEqual(
            Expression(Name('married'), Comparison('in'),
                       List([Const(True), Const(False)])),
            self.parser.parse('married in (True, False)'),
        )
        self.assertEqual(
            Expression(Name('smile'), Comparison('!='), Const(None)),
            self.parser.parse('(smile != None)'),
        )
        self.assertEqual(
            Expression(Name(['job', 'best', 'title']), Comparison('>'),
                       Const('none')),
            self.parser.parse('job.best.title > "none"'),
        )

    def test_string_comparisons(self):
        self.assertEqual(
            Expression(Name('name'), Comparison('~'), Const('gav')),
            self.parser.parse('name ~ "gav"'),
        )
        self.assertEqual(
            Expression(Name('name'), Comparison('!~'), Const('gav')),
            self.parser.parse('name !~ "gav"'),
        )
        self.assertEqual(
            Expression(Name('name'), Comparison('startswith'), Const('gav')),
            self.parser.parse('name startswith "gav"'),
        )
        self.assertEqual(
            Expression(Name('name'), Comparison('not startswith'), Const('rr')),
            self.parser.parse('name not startswith "rr"'),
        )
        self.assertEqual(
            Expression(Name('name'), Comparison('endswith'), Const('gav')),
            self.parser.parse('name endswith "gav"'),
        )
        self.assertEqual(
            Expression(Name('name'), Comparison('not endswith'), Const('gav')),
            self.parser.parse('name not endswith "gav"'),
        )

    def test_escaped_chars(self):
        self.assertEqual(
            Expression(Name('name'), Comparison('~'),
                       Const(u'Contains a "quoted" str, 年年有余')),
            self.parser.parse(u'name ~ "Contains a \\"quoted\\" str, 年年有余"'),
        )
        self.assertEqual(
            Expression(Name('options'), Comparison('='), Const(u'П и Щ')),
            self.parser.parse(u'options = "\\u041f \\u0438 \\u0429"'),
        )

    def test_numbers(self):
        self.assertEqual(
            Expression(Name('pk'), Comparison('>'), Const(5)),
            self.parser.parse('pk > 5'),
        )
        self.assertEqual(
            Expression(Name('rating'), Comparison('<='), Const(523)),
            self.parser.parse('rating <= 5.23e2'),
        )

    def test_logical(self):
        self.assertEqual(
            Expression(
                Expression(Name('age'), Comparison('>='), Const(18)),
                Logical('and'),
                Expression(Name('age'), Comparison('<='), Const(45)),
            ),
            self.parser.parse('age >= 18 and age <= 45'),
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
                              '(city = "Paris" and age <= 45)'),
        )

    def test_invalid_comparison(self):
        invalid_comparisons = (
            'foo > None',
            'b <= True',
            'c in False',
            '1 = 1',
            'a > b',
            'lol ~ None',
            'gav endswith 1',
            'nor not startswith False',
        )
        for expr in invalid_comparisons:
            self.assertRaises(DjangoQLParserError, self.parser.parse, expr)

    def test_entity_props(self):
        self.assertEqual(
            Expression(Name(['user', 'group', 'id']), Comparison('='),
                       Const(5)),
            self.parser.parse('user.group.id = 5'),
        )
