# Tests for djangoql.breakdown.explain_empty — the "where the query runs out
# of data" empty-result breakdown.
from django.contrib.auth.models import User
from django.test import TestCase

from djangoql.breakdown import explain, explain_empty

from ..models import Book


def _flatten(node, acc=None):
    """Depth-first list of every node in a breakdown tree."""
    if acc is None:
        acc = []
    if node is None:
        return acc
    acc.append(node)
    for child in node.get('children', ()):
        _flatten(child, acc)
    return acc


def _find(node, role):
    return [n for n in _flatten(node) if n['role'] == role]


class BreakdownBaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create(username='a')
        # Two Drama books rated 5, one Comics book rated 1.
        Book.objects.create(name='d1', author=cls.author, genre=1, rating=5.0)
        Book.objects.create(name='d2', author=cls.author, genre=1, rating=5.0)
        Book.objects.create(name='c1', author=cls.author, genre=2, rating=1.0)


class LazyTriggerTest(BreakdownBaseTest):
    def test_non_empty_result_returns_none(self):
        # The breakdown is only for the zero-rows case.
        result = explain_empty(Book.objects.all(), 'genre = 1')
        self.assertIsNone(result)

    def test_empty_search_returns_none(self):
        self.assertIsNone(explain_empty(Book.objects.all(), ''))
        self.assertIsNone(explain_empty(Book.objects.all(), '   '))

    def test_empty_result_returns_tree(self):
        # genre 3 has no rows -> a breakdown tree is produced.
        result = explain_empty(Book.objects.all(), 'genre = 3')
        self.assertIsNotNone(result)
        self.assertEqual(result['count'], 0)


class ExplainAlwaysTest(BreakdownBaseTest):
    """explain() always returns the per-node count tree (the on-demand
    breakdown), unlike explain_empty() which only fires on zero rows."""

    def test_non_empty_result_still_returns_tree(self):
        # genre = 1 -> 2 rows. explain_empty would return None here; explain
        # returns the tree with the real count.
        self.assertIsNone(explain_empty(Book.objects.all(), 'genre = 1'))
        tree = explain(Book.objects.all(), 'genre = 1')
        self.assertIsNotNone(tree)
        self.assertEqual(tree['count'], 2)
        self.assertEqual(tree['role'], 'leaf')

    def test_empty_search_returns_none(self):
        self.assertIsNone(explain(Book.objects.all(), ''))
        self.assertIsNone(explain(Book.objects.all(), '   '))

    def test_per_branch_counts(self):
        # genre = 1 (2 rows) and rating = 5 (2 rows) -> intersection 2 rows.
        tree = explain(Book.objects.all(), 'genre = 1 and rating = 5')
        self.assertEqual(tree['count'], 2)
        child_counts = sorted(c['count'] for c in tree['children'])
        self.assertEqual(child_counts, [2, 2])

    def test_zero_branch_flagged_in_non_empty_or(self):
        # genre = 1 (2 rows) or genre = 3 (0 rows) -> overall 2 rows, but the
        # dead branch is still surfaced.
        tree = explain(Book.objects.all(), 'genre = 1 or genre = 3')
        self.assertEqual(tree['count'], 2)
        dead = _find(tree, 'dead_or_branch')
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0]['text'], 'genre = 3')

    def test_and_has_higher_precedence_than_or(self):
        tree = explain(
            Book.objects.all(),
            'genre = 1 and rating = 5 or genre = 2',
        )

        self.assertEqual(tree['role'], 'or')
        self.assertEqual(tree['count'], 3)
        self.assertEqual(tree['children'][0]['role'], 'and')
        self.assertEqual(tree['children'][0]['count'], 2)
        self.assertEqual(tree['children'][1]['text'], 'genre = 2')
        self.assertEqual(tree['children'][1]['count'], 1)

    def test_max_nodes_truncates(self):
        tree = explain(
            Book.objects.all(),
            'genre = 1 and rating = 5 and rating = 5',
            max_nodes=1,
        )
        self.assertTrue(tree.get('truncated'))


class FlatAndChainTest(BreakdownBaseTest):
    def test_last_conjunct_kills_count(self):
        # genre = 1 -> 2 rows; adding rating = 1 -> 0 rows.
        # The final AND is the killer (both sides individually non-empty).
        tree = explain_empty(Book.objects.all(), 'genre = 1 and rating = 1')
        self.assertIsNotNone(tree)
        killers = _find(tree, 'killer_and')
        self.assertEqual(len(killers), 1)
        killer = killers[0]
        self.assertEqual(killer['count'], 0)
        # Both child leaves are individually non-empty.
        child_counts = sorted(c['count'] for c in killer['children'])
        self.assertEqual(child_counts, [1, 2])


class KillerIntersectionTest(BreakdownBaseTest):
    def test_both_sides_nonempty_intersection_zero(self):
        # genre = 1 (2 rows) AND genre = 2 (1 row) -> intersection 0.
        tree = explain_empty(
            Book.objects.all(),
            'genre = 1 and genre = 2',
        )
        killers = _find(tree, 'killer_and')
        self.assertEqual(len(killers), 1)
        self.assertEqual(killers[0]['count'], 0)
        # Leaf labels reconstructed from the AST.
        leaves = _find(tree, 'leaf')
        labels = {leaf['text'] for leaf in leaves}
        self.assertIn('genre = 1', labels)
        self.assertIn('genre = 2', labels)


class OrBranchTest(BreakdownBaseTest):
    def test_or_one_branch_zero_is_not_killer(self):
        # genre = 1 (2 rows) OR genre = 3 (0 rows) -> overall non-empty, so
        # explain_empty returns None. Use a wrapping AND to force emptiness.
        # genre = 3 (0) OR genre = 99 (0) -> both dead -> highlight branches.
        tree = explain_empty(
            Book.objects.all(),
            'genre = 3 or genre = 99',
        )
        self.assertIsNotNone(tree)
        # Root OR is zero, both branches dead.
        dead = _find(tree, 'dead_or_branch')
        self.assertEqual(len(dead), 2)
        for branch in dead:
            self.assertEqual(branch['count'], 0)
        # The OR node itself is not flagged killer_and.
        self.assertEqual(_find(tree, 'killer_and'), [])

    def test_or_inside_killer_and_dead_branch_flagged(self):
        # (genre = 3 or genre = 1) -> 2 rows; AND rating = 1 -> 0 rows.
        # Inside the OR, genre = 3 is a dead branch but genre = 1 is alive,
        # so the OR is alive; the top AND is the killer.
        tree = explain_empty(
            Book.objects.all(),
            '(genre = 3 or genre = 1) and rating = 1',
        )
        killers = _find(tree, 'killer_and')
        self.assertEqual(len(killers), 1)
        # The OR has one dead branch (genre = 3) but is itself non-empty.
        dead = _find(tree, 'dead_or_branch')
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0]['text'], 'genre = 3')


class NestedStructureTest(BreakdownBaseTest):
    def test_mixed_and_or_structure_locates_killer(self):
        # genre in (1, 2) -> 3 rows; AND rating = 99 -> 0 rows.
        tree = explain_empty(
            Book.objects.all(),
            'genre in (1, 2) and rating = 99',
        )
        self.assertEqual(tree['count'], 0)
        killers = _find(tree, 'killer_and')
        self.assertEqual(len(killers), 1)
        killer = killers[0]
        # left side (genre in (1, 2)) non-empty, right side (rating = 99) zero
        # -> this is a one-sided drop, still flagged as killer_and because the
        # AND collapses the count to zero.
        self.assertEqual(killer['count'], 0)


class AggregateAnnotationTest(TestCase):
    """A leaf referencing a derived/aggregate field must have its annotations
    applied before count() so the breakdown doesn't crash."""

    @classmethod
    def setUpTestData(cls):
        cls.prolific = User.objects.create(username='prolific')
        for i in range(3):
            Book.objects.create(name='b%d' % i, author=cls.prolific)
        cls.quiet = User.objects.create(username='quiet')

    def test_aggregate_leaf_count(self):
        from djangoql.extras import ExtrasSchema

        # No user has > 100 books -> empty result; breakdown must count the
        # aggregate leaf correctly (annotations threaded) without crashing.
        tree = explain_empty(
            User.objects.all(),
            'book__count > 100',
            schema=ExtrasSchema,
        )
        self.assertIsNotNone(tree)
        self.assertEqual(tree['count'], 0)
        # The single leaf counts users with > 100 books -> 0.
        leaves = _find(tree, 'leaf')
        self.assertEqual(len(leaves), 1)
        self.assertEqual(leaves[0]['count'], 0)

    def test_aggregate_in_killer_and(self):
        from djangoql.extras import ExtrasSchema

        # book__count > 0 -> prolific (1 user); username = "quiet" -> quiet (1).
        # Intersection empty -> killer AND, both sides individually non-empty.
        tree = explain_empty(
            User.objects.all(),
            'book__count > 0 and username = "quiet"',
            schema=ExtrasSchema,
        )
        killers = _find(tree, 'killer_and')
        self.assertEqual(len(killers), 1)
        child_counts = sorted(c['count'] for c in killers[0]['children'])
        self.assertEqual(child_counts, [1, 1])


class MaxNodeBudgetTest(BreakdownBaseTest):
    def test_oversized_ast_marked_truncated(self):
        # A long AND chain exceeding the budget must be marked truncated and
        # must NOT silently cap (the flag has to surface).
        search = ' and '.join('genre = 3' for _ in range(8))
        tree = explain_empty(
            Book.objects.all(),
            search,
            max_nodes=3,
        )
        self.assertIsNotNone(tree)
        self.assertTrue(tree.get('truncated'))

    def test_within_budget_not_truncated(self):
        tree = explain_empty(
            Book.objects.all(),
            'genre = 3 and rating = 1',
            max_nodes=50,
        )
        self.assertFalse(tree.get('truncated', False))


class LeafLabelTest(BreakdownBaseTest):
    def test_list_and_operators_rendered(self):
        tree = explain_empty(
            Book.objects.all(),
            'genre in (1, 2) and name = "zzz"',
        )
        labels = {leaf['text'] for leaf in _find(tree, 'leaf')}
        self.assertIn('genre in (1, 2)', labels)
        self.assertIn('name = "zzz"', labels)


class AdminEmptyBreakdownTest(TestCase):
    """The admin empty-state surfaces the breakdown as a warning message."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import User

        cls.user = User.objects.create_superuser(
            username='boss', email='boss@derp.rr', password='lol'
        )
        Book.objects.create(name='d', author=cls.user, genre=1, rating=5.0)

    def setUp(self):
        from django.contrib import admin as django_admin
        from django.test import RequestFactory

        self.factory = RequestFactory()
        self.book_admin = django_admin.site._registry[Book]

    def _request(self, path='/'):
        from django.contrib.messages.storage.fallback import FallbackStorage

        request = self.factory.get(path)
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_empty_djangoql_result_adds_breakdown_message(self):
        from django.contrib.messages import WARNING

        request = self._request()
        result, _ = self.book_admin.get_search_results(
            request,
            Book.objects.all(),
            'genre = 1 and rating = 1',
        )
        self.assertEqual(list(result), [])
        queued = request._messages._queued_messages
        # One warning: the empty-result breakdown.
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].level, WARNING)
        self.assertIn('genre = 1', str(queued[0].message))

    def test_non_empty_result_adds_no_message(self):
        request = self._request()
        result, _ = self.book_admin.get_search_results(
            request,
            Book.objects.all(),
            'genre = 1',
        )
        self.assertEqual([b.name for b in result], ['d'])
        self.assertEqual(len(request._messages._queued_messages), 0)

    def test_breakdown_disabled_adds_no_message(self):
        from unittest import mock

        request = self._request()
        with mock.patch.object(
            type(self.book_admin), 'djangoql_explain_empty', False
        ):
            result, _ = self.book_admin.get_search_results(
                request,
                Book.objects.all(),
                'genre = 1 and rating = 1',
            )
        self.assertEqual(list(result), [])
        self.assertEqual(len(request._messages._queued_messages), 0)
