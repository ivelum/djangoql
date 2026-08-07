# Tests for the core `suggested` flag and djangoql.extras derived fields.
from datetime import datetime

from django.contrib.auth.models import Group, User
from django.db.models import Count
from django.test import TestCase

from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema, IntField
from djangoql.serializers import DjangoQLSchemaSerializer

from ..models import Book


class HiddenFieldSchema(DjangoQLSchema):
    def get_fields(self, model):
        fields = list(super().get_fields(model))
        if model == Book:
            fields.append(IntField(name='secret', suggested=False))
        return fields


class SuggestedFlagTest(TestCase):
    def test_default_field_is_suggested(self):
        self.assertTrue(IntField(name='x').suggested)

    def test_unsuggested_field_hidden_from_serializer(self):
        data = DjangoQLSchemaSerializer().serialize(HiddenFieldSchema(Book))
        book_fields = data['models']['core.book']
        self.assertIn('name', book_fields)
        self.assertNotIn('secret', book_fields)

    def test_unsuggested_field_still_validates(self):
        # suggested=False hides a field from autocomplete but it must remain
        # usable in actual queries (validation/resolution still see it).
        from djangoql.parser import DjangoQLParser

        ast = DjangoQLParser().parse('secret > 0')
        HiddenFieldSchema(Book).validate(ast)  # must not raise


class _ProbeCountField(IntField):
    """Minimal annotation-backed field for testing the lazy hook."""

    name = 'probe'

    def get_annotations(self, path):
        return {'probe': Count('book')}

    def get_lookup(self, path, operator, value):
        from django.db.models import Q

        op, invert = self.get_operator(operator)
        q = Q(**{'probe%s' % op: value})
        return ~q if invert else q


class ProbeSchema(DjangoQLSchema):
    def get_fields(self, model):
        fields = list(super().get_fields(model))
        if model == User:
            fields.append(_ProbeCountField(model=User))
        return fields


class CollectAnnotationsTest(TestCase):
    def test_annotation_applied_only_when_field_used(self):
        used = apply_search(User.objects.all(), 'probe > 1', schema=ProbeSchema)
        self.assertIn('probe', used.query.annotations)

    def test_annotation_absent_when_field_unused(self):
        unused = apply_search(
            User.objects.all(),
            'username = "x"',
            schema=ProbeSchema,
        )
        self.assertNotIn('probe', unused.query.annotations)


class DatePartsTest(TestCase):
    def _where(self, search):
        from djangoql.extras import DatePartsSchemaMixin

        class S(DatePartsSchemaMixin, DjangoQLSchema):
            pass

        qs = apply_search(Book.objects.all(), search, schema=S)
        return str(qs.query).split('WHERE')[1].strip()

    def test_datetime_year(self):
        # SQLite expands __year on a DateTimeField to a BETWEEN range rather
        # than calling django_datetime_extract, so we verify the transform
        # works correctly by checking the filtered results instead.
        from django.contrib.auth.models import User
        from django.utils.timezone import make_aware

        author = User.objects.create_user('testauthor_year')
        Book.objects.create(
            name='Y2020',
            author=author,
            written=make_aware(datetime(2020, 6, 15, 12, 0)),
        )
        Book.objects.create(
            name='Y2021',
            author=author,
            written=make_aware(datetime(2021, 6, 15, 12, 0)),
        )
        from djangoql.extras import DatePartsSchemaMixin

        class S(DatePartsSchemaMixin, DjangoQLSchema):
            pass

        qs = apply_search(Book.objects.all(), 'written__year = 2020', schema=S)
        names = list(qs.values_list('name', flat=True))
        self.assertIn('Y2020', names)
        self.assertNotIn('Y2021', names)

    def test_datetime_hour(self):
        where = self._where('written__hour >= 9').lower()
        self.assertIn('hour', where)

    def test_date_field_month(self):
        where = self._where('published_date__month = 6').lower()
        self.assertIn('month', where)

    def test_time_field_minute(self):
        where = self._where('published_time__minute = 30').lower()
        self.assertIn('minute', where)

    def test_datetime_date_extract(self):
        where = self._where('written__date = "2020-01-01"').lower()
        self.assertIn('date', where)

    def test_time_extract_rejects_invalid_value(self):
        from djangoql.exceptions import DjangoQLSchemaError
        from djangoql.extras import DatePartsSchemaMixin

        class S(DatePartsSchemaMixin, DjangoQLSchema):
            pass

        with self.assertRaises(DjangoQLSchemaError):
            apply_search(Book.objects.all(), 'written__time = "nope"', schema=S)

    def test_time_extract_accepts_value_list(self):
        # The `in (...)` path runs get_lookup_value over a list of times.
        where = self._where('written__time in ("09:30", "10:30")').lower()
        self.assertIn('time', where)

    def test_datetime_time_extract(self):
        from django.utils.timezone import make_aware

        author = User.objects.create_user('testauthor_time')
        morning = Book.objects.create(
            name='morn',
            author=author,
            written=make_aware(datetime(2020, 1, 1, 9, 30)),
        )
        evening = Book.objects.create(
            name='eve',
            author=author,
            written=make_aware(datetime(2020, 1, 1, 18, 45)),
        )
        from djangoql.extras import DatePartsSchemaMixin

        class S(DatePartsSchemaMixin, DjangoQLSchema):
            pass

        qs = apply_search(
            Book.objects.all(), 'written__time = "09:30"', schema=S
        )
        names = set(qs.values_list('name', flat=True))
        self.assertIn('morn', names)
        self.assertNotIn('eve', names)
        # Clean up to avoid leaking into other tests
        morning.delete()
        evening.delete()
        author.delete()


class _CountSchemaFK(DjangoQLSchema):
    """Hand-built schema adding only User.book__count (reverse FK)."""

    def get_fields(self, model):
        from djangoql.extras import CountField, _owner_lookup

        fields = list(super().get_fields(model))
        if model == User:
            rel = User._meta.get_field('book')  # ManyToOneRel
            fields.append(
                CountField(
                    model=User,
                    relation_name='book',
                    related_model=rel.related_model,
                    owner_lookup=_owner_lookup(rel),
                    name='book__count',
                )
            )
        return fields


class CountFKTest(TestCase):
    def setUp(self):
        self.prolific = User.objects.create(username='prolific')
        self.quiet = User.objects.create(username='quiet')
        for i in range(3):
            Book.objects.create(name='b%d' % i, author=self.prolific)

    def _usernames(self, search):
        qs = apply_search(User.objects.all(), search, schema=_CountSchemaFK)
        return set(qs.values_list('username', flat=True))

    def test_count_gt(self):
        self.assertEqual(self._usernames('book__count > 2'), {'prolific'})

    def test_count_zero_matches_empty(self):
        # Coalesce(...,0) makes "= 0" match users with no books.
        self.assertIn('quiet', self._usernames('book__count = 0'))
        self.assertNotIn('prolific', self._usernames('book__count = 0'))

    def test_count_lazy(self):
        qs = apply_search(
            User.objects.all(), 'username = "x"', schema=_CountSchemaFK
        )
        self.assertEqual(qs.query.annotations, {})

    def test_count_not_nullable(self):
        from djangoql.exceptions import DjangoQLSchemaError

        with self.assertRaises(DjangoQLSchemaError):
            apply_search(
                User.objects.all(),
                'book__count = None',
                schema=_CountSchemaFK,
            )


class CountM2MTest(TestCase):
    """Forward M2M relation count via ExtrasSchema (flat `groups__count`)."""

    def setUp(self):
        self.g1 = Group.objects.create(name='g1')
        self.g2 = Group.objects.create(name='g2')
        self.member = User.objects.create(username='member')
        self.member.groups.add(self.g1, self.g2)
        self.loner = User.objects.create(username='loner')

    def _usernames(self, search):
        from djangoql.extras import ExtrasSchema

        qs = apply_search(User.objects.all(), search, schema=ExtrasSchema)
        return set(qs.values_list('username', flat=True))

    def test_m2m_count_gt(self):
        self.assertEqual(self._usernames('groups__count > 1'), {'member'})

    def test_m2m_count_zero(self):
        self.assertIn('loner', self._usernames('groups__count = 0'))


class AutoAggregateTest(TestCase):
    def setUp(self):
        self.u = User.objects.create(username='u')
        Book.objects.create(name='a', author=self.u, rating=2.0, price=5)
        Book.objects.create(name='b', author=self.u, rating=4.0, price=7)
        self.v = User.objects.create(username='v')

    def _usernames(self, search):
        from djangoql.extras import ExtrasSchema

        qs = apply_search(User.objects.all(), search, schema=ExtrasSchema)
        return set(qs.values_list('username', flat=True))

    def test_auto_count(self):
        self.assertEqual(self._usernames('book__count = 2'), {'u'})

    def test_auto_numeric_aggregate(self):
        self.assertEqual(self._usernames('book.price__sum >= 12'), {'u'})

    def test_pk_and_fk_excluded(self):
        from djangoql.extras import ExtrasSchema

        names = set(ExtrasSchema(User).models['auth.user'].keys())
        self.assertIn('book__count', names)  # flat count kept (hidden)
        # Numeric aggregates are no longer schema fields at all (synthesized on
        # demand via dot syntax); pk/fk source exclusion is verified in
        # DotAggregateTest.test_pk_and_fk_not_aggregatable.
        self.assertNotIn('book__rating__sum', names)
        self.assertNotIn('book__id__sum', names)

    def test_multiple_aggregates_are_independent(self):
        # Two to-many aggregates in one query must not multiply each other.
        self.u.groups.clear()
        result = self._usernames('book__count = 2 and groups__count = 0')
        self.assertEqual(result, {'u'})

    def test_nested_one_hop(self):
        from djangoql.extras import ExtrasSchema

        qs = apply_search(
            Book.objects.all(),
            'author.book__count > 1',
            schema=ExtrasSchema,
        )
        names = set(qs.values_list('name', flat=True))
        self.assertEqual(names, {'a', 'b'})

    def test_date_and_count_compose(self):
        from djangoql.extras import ExtrasSchema

        user_fields = set(ExtrasSchema(User).models['auth.user'].keys())
        self.assertIn('date_joined__year', user_fields)
        self.assertIn('book__count', user_fields)

    def test_introspect_book_with_hidden_m2m(self):
        # Book.similar_books has related_name='+' (hidden reverse).
        # Introspecting Book with ExtrasSchema must not crash, and a plain
        # query must work.
        from djangoql.extras import ExtrasSchema

        qs = apply_search(Book.objects.all(), 'name = "a"', schema=ExtrasSchema)
        self.assertEqual(set(qs.values_list('name', flat=True)), {'a'})
        book_fields = set(ExtrasSchema(Book).models['core.book'].keys())
        self.assertNotIn('similar_books__count', book_fields)

    def test_reverse_m2m_count(self):
        # Group has a reverse M2M to User (User.groups). Searching Group,
        # user__count must count members (exercises _owner_lookup for
        # reverse M2M).
        from djangoql.extras import ExtrasSchema

        g = Group.objects.create(name='g')
        self.u.groups.add(g)
        qs = apply_search(
            Group.objects.all(),
            'user__count > 0',
            schema=ExtrasSchema,
        )
        self.assertEqual(set(qs.values_list('name', flat=True)), {'g'})


class DotAggregateTest(TestCase):
    """Numeric aggregates use dot syntax: <relation>.<numfield>__<agg>."""

    def setUp(self):
        self.u = User.objects.create(username='u')
        Book.objects.create(name='a', author=self.u, rating=2.0, price=5)
        Book.objects.create(name='b', author=self.u, rating=4.0, price=7)
        self.v = User.objects.create(username='v')
        Book.objects.create(name='c', author=self.v, rating=10.0, price=20)

    def _usernames(self, search):
        from djangoql.extras import ExtrasSchema

        qs = apply_search(User.objects.all(), search, schema=ExtrasSchema)
        return set(qs.values_list('username', flat=True))

    def test_dot_avg(self):
        # u avg = 3.0, v avg = 10.0
        self.assertEqual(self._usernames('book.rating__avg > 5'), {'v'})

    def test_dot_sum(self):
        # u sum = 6.0, v sum = 10.0
        self.assertEqual(self._usernames('book.rating__sum < 8'), {'u'})

    def test_dot_min_max(self):
        self.assertEqual(self._usernames('book.rating__min >= 10'), {'v'})
        self.assertEqual(self._usernames('book.rating__max <= 4'), {'u'})

    def test_dot_price_sum_decimal_source(self):
        self.assertEqual(self._usernames('book.price__sum >= 12'), {'u', 'v'})
        self.assertEqual(self._usernames('book.price__sum > 15'), {'v'})

    def test_dot_avg_none_validates(self):
        # avg/sum/min/max return SQL NULL for an empty set, so "= None" is a
        # valid, non-raising query.
        from djangoql.extras import ExtrasSchema
        from djangoql.parser import DjangoQLParser

        ast = DjangoQLParser().parse('book.rating__avg = None')
        ExtrasSchema(User).validate(ast)  # must not raise

    def test_dot_avg_none_matches_user_with_no_books(self):
        User.objects.create(username='no_books')
        result = self._usernames('book.rating__avg = None')
        self.assertIn('no_books', result)
        self.assertNotIn('u', result)

    def test_flat_numeric_aggregate_removed(self):
        # The old flat form is gone; numeric aggregates must use dot syntax.
        from djangoql.exceptions import DjangoQLSchemaError

        with self.assertRaises(DjangoQLSchemaError):
            self._usernames('book__rating__sum > 0')

    def test_pk_and_fk_not_aggregatable(self):
        from djangoql.exceptions import DjangoQLSchemaError

        for bad in ('book.id__sum', 'book.author__sum', 'book.object_id__sum'):
            with self.assertRaises(DjangoQLSchemaError):
                self._usernames('%s > 0' % bad)

    def test_nested_numeric_two_hops(self):
        # Search Book: author.book.rating__sum = sum of ratings across the
        # books written by this book's author.
        from djangoql.extras import ExtrasSchema

        qs = apply_search(
            Book.objects.all(),
            'author.book.rating__sum >= 6',
            schema=ExtrasSchema,
        )
        # u's books a,b: 2+4=6; v's book c: 10 — all satisfy >= 6.
        self.assertEqual(
            set(qs.values_list('name', flat=True)), {'a', 'b', 'c'}
        )


class DerivedFieldsHiddenTest(TestCase):
    """Derived fields stay usable but are hidden from autocomplete."""

    def _serialized(self):
        from djangoql.extras import ExtrasSchema

        data = DjangoQLSchemaSerializer().serialize(ExtrasSchema(User))
        return data['models']['auth.user']

    def test_count_hidden_from_autocomplete(self):
        self.assertNotIn('book__count', self._serialized())

    def test_date_parts_hidden_from_autocomplete(self):
        self.assertNotIn('date_joined__year', self._serialized())

    def test_normal_fields_and_relations_still_suggested(self):
        fields = self._serialized()
        self.assertIn('username', fields)
        self.assertIn('book', fields)  # the relation itself stays suggestable

    def test_hidden_count_still_resolves(self):
        from djangoql.extras import ExtrasSchema
        from djangoql.parser import DjangoQLParser

        ast = DjangoQLParser().parse('book__count = 0')
        ExtrasSchema(User).validate(ast)  # must not raise


class ErrorHintTest(TestCase):
    """The 'Unknown field' error hides derived fields from the choice list and
    points at the derived syntax instead."""

    def _error_message(self, search):
        from djangoql.exceptions import DjangoQLSchemaError
        from djangoql.extras import ExtrasSchema

        try:
            apply_search(User.objects.all(), search, schema=ExtrasSchema)
        except DjangoQLSchemaError as exc:
            return str(exc)
        self.fail('expected DjangoQLSchemaError')

    def test_choices_exclude_hidden_derived_fields(self):
        msg = self._error_message('nope = 1')
        # Isolate the "Possible choices" list (before the hint sentence).
        choices = msg.split('Relation aggregates')[0]
        self.assertIn('username', choices)
        self.assertNotIn('__count', choices)
        self.assertNotIn('__year', choices)

    def test_hint_mentions_aggregate_and_date_syntax(self):
        msg = self._error_message('nope = 1')
        self.assertIn('__count', msg)
        self.assertIn('sum,avg,min,max', msg)
        self.assertIn('__year', msg)


class BackwardCompatTest(TestCase):
    def test_default_schema_unchanged(self):
        # Stock schema adds no annotations and exposes no derived fields.
        qs = apply_search(Book.objects.all(), 'name = "x"')
        self.assertEqual(qs.query.annotations, {})
        names = set(DjangoQLSchema(Book).models['core.book'].keys())
        self.assertNotIn('written__year', names)
        self.assertNotIn('author__count', names)

    def test_stock_field_get_annotations_empty(self):
        self.assertEqual(IntField(name='x').get_annotations([]), {})


class AggregateSynthesisEdgeCasesTest(TestCase):
    """resolve_unknown / _synthesize_aggregate fall-throughs + hint helpers."""

    def _error(self, qs, search):
        from djangoql.exceptions import DjangoQLSchemaError
        from djangoql.extras import ExtrasSchema

        with self.assertRaises(DjangoQLSchemaError):
            apply_search(qs, search, schema=ExtrasSchema)

    def test_dot_name_without_aggregate_suffix_is_unknown(self):
        # 'book.nonexistent' — the trailing part has no '__', so it can't be a
        # numeric aggregate; falls through to the "unknown field" error.
        self._error(User.objects.all(), 'book.nonexistent = 1')

    def test_aggregate_over_missing_source_is_unknown(self):
        # 'book.bogus__sum' — 'bogus' is not a field on the related model.
        self._error(User.objects.all(), 'book.bogus__sum > 0')

    def test_aggregate_over_hidden_reverse_relation_is_unknown(self):
        # Book.similar_books has related_name='+' (hidden reverse): no usable
        # owner lookup, so no aggregate can be synthesized through it.
        self._error(Book.objects.all(), 'similar_books.rating__sum > 0')

    def test_hint_count_only_when_related_has_no_numeric_field(self):
        # Group's to-many relations point at models with no aggregatable numeric
        # field, so the hint offers a __count example but no .<field>__sum one.
        from djangoql.exceptions import DjangoQLSchemaError
        from djangoql.extras import ExtrasSchema

        try:
            apply_search(Group.objects.all(), 'nope = 1', schema=ExtrasSchema)
        except DjangoQLSchemaError as exc:
            msg = str(exc)
        else:
            self.fail('expected DjangoQLSchemaError')
        self.assertIn('__count', msg)
        # The concrete example list (after "e.g.") must not contain a dot-form
        # numeric aggregate, since none is available.
        example_part = msg.split('e.g.')[-1]
        self.assertNotIn('__sum', example_part)
