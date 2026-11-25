"""Tests for the LLM schema-description helper and its management command.

``describe_schema_for_llm`` turns a DjangoQLSchema into a self-contained,
machine-readable description of the whole search space (fields, types,
relations, allowed operators, examples) suitable for an LLM prompt. The
``djangoql_describe_schema_for_llm`` command prints that description as JSON.
"""

import json
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from djangoql.extras import (
    AggregateSchemaMixin,
    AutocompleteSchemaMixin,
    DatePartsSchemaMixin,
)
from djangoql.llm import _build_schema_ir, describe_schema_for_llm
from djangoql.parser import DjangoQLParser
from djangoql.schema import DjangoQLSchema

from ..models import Book


class DerivedSchema(AggregateSchemaMixin, DatePartsSchemaMixin, DjangoQLSchema):
    include = (Book, User)


class DerivedCapabilitiesTest(TestCase):
    def test_capabilities_detected_from_all_fields(self):
        # Derived fields are suggested=False, but detection scans schema.models
        ir = _build_schema_ir(DerivedSchema(Book), 50)
        caps = ir['capabilities']
        self.assertIn('year', caps['date_parts'])
        self.assertIn('hour', caps['time_parts'])
        self.assertTrue(caps['has_date_extract'])
        self.assertTrue(caps['has_time_extract'])
        # User has a reverse to-many to Book -> book__count (CountField)
        self.assertTrue(caps['relation_count'])

    def test_time_parts_never_land_in_date_parts(self):
        ir = _build_schema_ir(DerivedSchema(Book), 50)
        self.assertNotIn('hour', ir['capabilities']['date_parts'])

    def test_plain_schema_has_empty_capabilities(self):
        ir = _build_schema_ir(DjangoQLSchema(Book), 50)
        caps = ir['capabilities']
        self.assertEqual([], caps['date_parts'])
        self.assertEqual([], caps['time_parts'])
        self.assertFalse(caps['relation_count'])

    def test_derived_fields_absent_but_base_present(self):
        ir = _build_schema_ir(DerivedSchema(Book), 50)
        book = ir['models']['core.book']
        self.assertIn('written', book)  # base datetime field stays
        self.assertNotIn('written__year', book)
        self.assertNotIn('written__date', book)
        user = ir['models']['auth.user']
        self.assertNotIn('book__count', user)

    def test_suggested_true_derived_field_still_excluded(self):
        from djangoql.extras import DatePartField

        class SurfacedSchema(DjangoQLSchema):
            def get_fields(self, model):
                fields = list(super().get_fields(model))
                if model == Book:
                    f = DatePartField('written', 'year', model=model)
                    f.suggested = True  # force it visible
                    fields.append(f)
                return fields

        ir = _build_schema_ir(SurfacedSchema(Book), 50)
        self.assertNotIn('written__year', ir['models']['core.book'])

    def test_json_date_legend_advertises_part_lookups(self):
        bundle = describe_schema_for_llm(DerivedSchema(Book))
        lookups = bundle['operators_by_type']['date'].get('lookups', '')
        self.assertIn('year', lookups)
        self.assertIn('<field>__', lookups)

    def test_json_datetime_legend_advertises_time_and_extracts(self):
        bundle = describe_schema_for_llm(DerivedSchema(Book))
        lookups = bundle['operators_by_type']['datetime'].get('lookups', '')
        self.assertIn('hour', lookups)
        self.assertIn('__date', lookups)
        self.assertIn('__time', lookups)

    def test_json_relation_legend_advertises_aggregates(self):
        bundle = describe_schema_for_llm(DerivedSchema(Book))
        agg = bundle['operators_by_type']['relation'].get('aggregates', '')
        self.assertIn('__count', agg)
        self.assertIn('sum', agg)

    def test_json_plain_schema_has_no_capability_notes(self):
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        self.assertNotIn('lookups', bundle['operators_by_type']['date'])
        self.assertNotIn('aggregates', bundle['operators_by_type']['relation'])

    def test_compact_header_lists_capabilities_once(self):
        text = describe_schema_for_llm(DerivedSchema(Book), format='compact')
        self.assertIn('__count', text)
        self.assertIn('year', text)
        # the derived fields are not emitted as their own lines
        self.assertNotIn('written__year', text)
        self.assertNotIn('book__count  ', text)

    def test_datetime_example_omits_undetected_capabilities(self):
        from djangoql.llm import _apply_capabilities_to_legend, _operator_legend

        legend = _operator_legend()
        caps = {
            'date_parts': [],
            'time_parts': ['hour', 'minute', 'second'],
            'has_date_extract': False,
            'has_time_extract': False,
            'relation_count': False,
        }
        _apply_capabilities_to_legend(legend, caps)
        note = legend['datetime']['lookups']
        self.assertIn('hour', note)
        self.assertNotIn('__year', note)  # not detected -> not claimed
        self.assertNotIn('__date', note)  # not detected -> not claimed

    def test_date_example_reflects_detected_parts(self):
        from djangoql.llm import _apply_capabilities_to_legend, _operator_legend

        legend = _operator_legend()
        caps = {
            'date_parts': ['year', 'month'],
            'time_parts': [],
            'has_date_extract': False,
            'has_time_extract': False,
            'relation_count': False,
        }
        _apply_capabilities_to_legend(legend, caps)
        self.assertIn('year', legend['date']['lookups'])
        # date-only capability must not claim the datetime-only __date extract
        self.assertNotIn('__date', legend['datetime']['lookups'])


class AuthorPickerSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    include = (Book, User)
    autocomplete = {
        Book: {
            'author': {
                'queryset': lambda s: User.objects.filter(
                    username__icontains=s,
                ),
                'search_fields': ['username'],
            },
        },
    }


class ExcludeUserSchema(DjangoQLSchema):
    exclude = ()

    def get_fields(self, model):
        if model == Book:
            return [
                'name',
                'rating',
                'is_published',
                'author',
                'published_date',
            ]
        return super().get_fields(model)


class DescribeSchemaForLLMTest(TestCase):
    def setUp(self):
        self.bundle = describe_schema_for_llm(DjangoQLSchema(Book))

    def test_top_level_keys(self):
        for key in (
            'start_model',
            'grammar',
            'operators_by_type',
            'models',
            'examples',
        ):
            self.assertIn(key, self.bundle)

    def test_start_model_is_the_root(self):
        self.assertEqual('core.book', self.bundle['start_model'])

    def test_models_contains_root_and_related(self):
        models = self.bundle['models']
        self.assertIn('core.book', models)
        self.assertIn('auth.user', models)

    def test_operator_legend_is_emitted_once_by_type(self):
        legend = self.bundle['operators_by_type']
        self.assertIn('>', legend['float']['operators'])
        self.assertIn('~', legend['str']['operators'])
        self.assertIn('startswith', legend['str']['operators'])
        self.assertEqual({'=', '!='}, set(legend['bool']['operators']))
        self.assertIn('relation', legend)
        self.assertIn('object_reference', legend)

    def test_grammar_documents_operator_lookup(self):
        self.assertIn('operators_by_type', self.bundle['grammar']['operators'])

    def test_fields_never_repeat_operators_or_examples(self):
        for field in self.bundle['models']['core.book'].values():
            if isinstance(field, dict):
                self.assertNotIn('operators', field)
                self.assertNotIn('example', field)

    def test_plain_scalar_field_is_a_bare_type_string(self):
        # is_published is a non-null bool with no metadata -> bare "bool"
        self.assertEqual(
            'bool', self.bundle['models']['core.book']['is_published']
        )

    def test_nullable_field_uses_question_mark_suffix(self):
        # published_date is null=True and has no metadata -> "date?"
        self.assertEqual(
            'date?', self.bundle['models']['core.book']['published_date']
        )
        # rating is a nullable float with no metadata -> "float?"
        self.assertEqual('float?', self.bundle['models']['core.book']['rating'])

    def test_field_with_metadata_is_an_object_with_type(self):
        # name carries verbose_name/help_text -> object, type is 'str'
        name = self.bundle['models']['core.book']['name']
        self.assertEqual('str', name['type'])
        self.assertEqual('Title', name['label'])
        self.assertEqual('The title of the book', name['help_text'])

    def test_choice_field_object_lists_labels(self):
        genre = self.bundle['models']['core.book']['genre']
        self.assertEqual(['Drama', 'Comics', 'Other'], genre['choices'])

    def test_relation_field_object_points_at_related_model(self):
        author = self.bundle['models']['core.book']['author']
        self.assertEqual('auth.user', author['relates_to'])
        self.assertTrue(author['type'].startswith('relation'))

    def test_object_reference_uses_its_operator_class(self):
        bundle = describe_schema_for_llm(AuthorPickerSchema(Book))
        author = bundle['models']['core.book']['author']
        self.assertTrue(author['object_reference'])
        self.assertEqual(
            ['=', '!=', 'in', 'not in'],
            bundle['operators_by_type']['object_reference']['operators'],
        )

    def test_grammar_warns_there_is_no_standalone_not(self):
        self.assertIn('negation', self.bundle['grammar'])

    def test_examples_actually_parse(self):
        parser = DjangoQLParser()
        for query in self.bundle['examples']:
            parser.parse(query)

    def test_grammar_is_not_shared_between_calls(self):
        b1 = describe_schema_for_llm(DjangoQLSchema(Book))
        b1['grammar']['shape'] = 'MUTATED'
        b2 = describe_schema_for_llm(DjangoQLSchema(Book))
        self.assertNotEqual('MUTATED', b2['grammar']['shape'])

    def test_json_legend_has_fallback_for_custom_type(self):
        from djangoql.llm import _render_json

        ir = {
            'start_model': 'x.y',
            'models': {'x.y': {'f': {'type': 'geo', 'nullable': False}}},
        }
        bundle = _render_json(ir)
        self.assertEqual(
            ['=', '!=', 'in', 'not in'],
            bundle['operators_by_type']['geo']['operators'],
        )


class DjangoqlSchemaCommandTest(TestCase):
    def _run(self, *args):
        out = StringIO()
        call_command('djangoql_describe_schema_for_llm', *args, stdout=out)
        return out.getvalue()

    def test_outputs_valid_json_for_a_model(self):
        data = json.loads(self._run('core.Book'))
        self.assertEqual('core.book', data['start_model'])
        self.assertIn('rating', data['models']['core.book'])

    def test_unknown_model_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._run('core.Nonexistent')

    def test_bad_model_format_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._run('BookWithoutAppLabel')

    def test_custom_schema_limits_the_fields(self):
        data = json.loads(
            self._run(
                'core.Book',
                '--schema',
                'core.tests.test_llm.ExcludeUserSchema',
            ),
        )
        book_fields = set(data['models']['core.book'].keys())
        self.assertEqual(
            {'name', 'rating', 'is_published', 'author', 'published_date'},
            book_fields,
        )

    def test_bad_schema_path_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._run('core.Book', '--schema', 'no.such.Schema')

    def test_indent_option_is_respected(self):
        # indent=0 -> newlines but no leading spaces; default -> indented
        compact = self._run('core.Book', '--indent', '0')
        self.assertNotIn('\n  "start_model"', compact)

    def test_max_fk_options_flag_is_passed_through(self):
        # With the gate at 0, auto FK values are disabled; similar_books
        # (a non-sensitive relation) must carry no related_values.
        Book.objects.create(
            name='Dune',
            author=User.objects.create(username='ada'),
        )
        data = json.loads(self._run('core.Book', '--max-fk-options', '0'))
        similar = data['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
        self.assertEqual({}, data['dictionaries'])

    def test_compact_format_prints_text(self):
        out = self._run('core.Book', '--format', 'compact')
        self.assertIn('start model: core.book', out)
        self.assertIn('-> auth.user', out)
        # compact output is not JSON
        with self.assertRaises(ValueError):
            json.loads(out)

    def test_json_is_the_default_format(self):
        data = json.loads(self._run('core.Book'))
        self.assertIn('operators_by_type', data)


class RelationValuesTest(TestCase):
    def _book(self, name):
        author = User.objects.create(username='u-%s' % name)
        return Book.objects.create(name=name, author=author)

    def test_auto_emits_related_values_for_small_relation(self):
        # similar_books -> Book (non-sensitive). A handful of books means few
        # distinct names, so auto mode should surface them -- once, in the
        # shared dictionaries block, referenced by match_field.
        for n in ('Dune', 'Solaris', 'It'):
            self._book(n)
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        similar = bundle['models']['core.book']['similar_books']
        self.assertEqual('name', similar['match_field'])
        self.assertEqual(
            {'Dune', 'Solaris', 'It'},
            set(bundle['dictionaries']['core.book']['name']),
        )

    def test_auto_skips_relation_over_threshold(self):
        for n in ('a', 'b', 'c'):
            self._book(n)
        bundle = describe_schema_for_llm(DjangoQLSchema(Book), max_fk_options=2)
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
        self.assertNotIn('core.book', bundle['dictionaries'])

    def test_max_fk_options_zero_disables_auto(self):
        self._book('Dune')
        bundle = describe_schema_for_llm(DjangoQLSchema(Book), max_fk_options=0)
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
        self.assertEqual({}, bundle['dictionaries'])

    def test_auto_never_touches_sensitive_target_model(self):
        # author -> auth.User is sensitive: no values, and never the password.
        self._book('Dune')
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        author = bundle['models']['core.book']['author']
        self.assertNotIn('match_field', author)
        self.assertNotIn('auth.user', bundle['dictionaries'])
        self.assertNotIn('password', json.dumps(bundle))

    def test_auto_skips_custom_auth_user_model(self):
        # A custom AUTH_USER_MODEL living outside the built-in sensitive
        # apps (e.g. 'myapp.User') must be excluded from auto mode too, not
        # just models in SENSITIVE_TARGET_APP_LABELS. Pretend Book itself is
        # the user model (core app, not otherwise flagged as sensitive) via
        # similar_books, a self-relation on Book.
        for n in ('Dune', 'Solaris'):
            self._book(n)
        with mock.patch('djangoql.llm.get_user_model', return_value=Book):
            bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
        self.assertNotIn('core.book', bundle['dictionaries'])

    def test_distinct_values_logs_on_error(self):
        # A bad field name blows up inside the try/except in _distinct_values;
        # it must still return None, but the error must no longer be silent.
        from djangoql.llm import _distinct_values

        with self.assertLogs('djangoql.llm', level='WARNING'):
            result = _distinct_values(Book, 'no_such_field', 100)
        self.assertIsNone(result)

    def test_str_examples_logs_on_error(self):
        # count() raising blows up inside the try/except in _str_examples;
        # it must still return None, but the error must no longer be silent.
        from unittest.mock import patch

        from djangoql.llm import _str_examples

        with patch.object(
            Book.objects, 'count', side_effect=RuntimeError('boom')
        ):
            with self.assertLogs('djangoql.llm', level='WARNING'):
                result = _str_examples(Book, 100)
        self.assertIsNone(result)

    def test_default_match_field_prefers_visible_str_field(self):
        # The heuristic must pick from schema-visible fields (never password).
        from djangoql.llm import _default_match_field

        schema = DjangoQLSchema(Book)
        self.assertEqual('name', _default_match_field(schema, 'core.book'))

    def test_default_match_field_prefers_username_over_first_alphabetical(self):
        # auth.User has no 'name' field; alphabetically the first suggested
        # str field is 'email', but 'username' is the actual identifier and
        # must win via the preferred-fields priority list.
        from djangoql.llm import _default_match_field

        schema = DjangoQLSchema(Book)
        self.assertEqual('username', _default_match_field(schema, 'auth.user'))

    def test_default_match_field_prefers_priority_list_over_alphabetical(self):
        from djangoql.llm import _default_match_field

        class _StubField:
            def __init__(self, ftype, suggested=True):
                self.type = ftype
                self.suggested = suggested

        class _StubSchema:
            models = {
                'x.y': {
                    'aardvark': _StubField('str', suggested=True),
                    'nazwa': _StubField('str', suggested=True),
                },
            }

        # 'aardvark' sorts first alphabetically, but 'nazwa' is on the
        # preferred-identifier list and must win.
        self.assertEqual('nazwa', _default_match_field(_StubSchema(), 'x.y'))

    def test_default_match_field_skips_unsuggested_fields(self):
        from djangoql.llm import _default_match_field

        class _StubField:
            def __init__(self, ftype, suggested=True):
                self.type = ftype
                self.suggested = suggested

        class _StubSchema:
            models = {
                'x.y': {
                    'secret': _StubField('str', suggested=False),
                    'label': _StubField('str', suggested=True),
                },
            }

        # 'secret' comes first but is hidden -> must fall through to 'label'
        self.assertEqual('label', _default_match_field(_StubSchema(), 'x.y'))

    def test_fk_options_name_overrides_sensitive_exclusion(self):
        User.objects.create(username='ada')
        User.objects.create(username='alan')

        class ForcedSchema(DjangoQLSchema):
            fk_options = {Book: {'author': 'username'}}

        bundle = describe_schema_for_llm(ForcedSchema(Book))
        author = bundle['models']['core.book']['author']
        self.assertEqual('username', author['match_field'])
        self.assertEqual(
            {'ada', 'alan'},
            set(bundle['dictionaries']['auth.user']['username']),
        )

    def test_fk_options_list_emits_values_per_field(self):
        User.objects.create(username='ada', email='ada@x.io')

        class ListSchema(DjangoQLSchema):
            fk_options = {Book: {'author': ['username', 'email']}}

        bundle = describe_schema_for_llm(ListSchema(Book))
        author = bundle['models']['core.book']['author']
        self.assertEqual(['username', 'email'], author['match_fields'])
        user_dict = bundle['dictionaries']['auth.user']
        self.assertEqual(['ada'], user_dict['username'])
        self.assertEqual(['ada@x.io'], user_dict['email'])

    def test_fk_options_str_emits_related_examples(self):
        User.objects.create(username='ada')

        class StrSchema(DjangoQLSchema):
            fk_options = {Book: {'author': '__str__'}}

        bundle = describe_schema_for_llm(StrSchema(Book))
        author = bundle['models']['core.book']['author']
        self.assertEqual('__str__', author['match_field'])
        self.assertEqual(
            ['ada'], bundle['dictionaries']['auth.user']['__str__']
        )

    def test_fk_options_false_emits_nothing(self):
        User.objects.create(username='ada')

        class OffSchema(DjangoQLSchema):
            fk_options = {Book: {'author': False}}

        bundle = describe_schema_for_llm(OffSchema(Book))
        author = bundle['models']['core.book']['author']
        self.assertNotIn('match_field', author)
        self.assertNotIn('match_fields', author)
        self.assertNotIn('auth.user', bundle['dictionaries'])

    def test_fk_options_false_on_nonsensitive_relation(self):
        # author -> auth.User is sensitive, so auto mode would exclude it
        # regardless of the False spec; similar_books -> Book is not, so an
        # empty reference here can only be explained by the False dispatch arm.
        # (Other relations to core.book still populate its dictionary entry.)
        for n in ('Dune', 'Solaris'):
            self._book(n)

        class OffSchema(DjangoQLSchema):
            fk_options = {Book: {'similar_books': False}}

        bundle = describe_schema_for_llm(OffSchema(Book))
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)

    def test_fk_options_true_ignores_threshold(self):
        # Test on similar_books -> Book, whose default identifying field is
        # deterministically 'name'. (For auth.User the default is now
        # 'username', via the preferred-identifier priority list.)
        for n in ('Dune', 'Solaris'):
            self._book(n)

        class ForceSchema(DjangoQLSchema):
            fk_options = {Book: {'similar_books': True}}

        # threshold of 1 would normally skip two distinct names
        bundle = describe_schema_for_llm(ForceSchema(Book), max_fk_options=1)
        similar = bundle['models']['core.book']['similar_books']
        self.assertEqual('name', similar['match_field'])
        self.assertEqual(
            {'Dune', 'Solaris'},
            set(bundle['dictionaries']['core.book']['name']),
        )

    def test_fk_options_int_bypasses_cap_and_global_threshold(self):
        # An integer spec is a per-relation limit: it must surface EVERY value
        # up to that limit, overriding both the MAX_SUGGESTED_VALUES cap (which
        # True would hit) and the global max_fk_options gate (0 here). 25
        # distinct names > 20 (MAX_SUGGESTED_VALUES) proves the cap is bypassed.
        from djangoql.llm import MAX_SUGGESTED_VALUES

        names = {'book-%02d' % i for i in range(MAX_SUGGESTED_VALUES + 5)}
        for n in names:
            self._book(n)

        class IntSchema(DjangoQLSchema):
            fk_options = {Book: {'similar_books': 1000}}

        bundle = describe_schema_for_llm(IntSchema(Book), max_fk_options=0)
        similar = bundle['models']['core.book']['similar_books']
        self.assertEqual('name', similar['match_field'])
        self.assertEqual(
            names, set(bundle['dictionaries']['core.book']['name'])
        )

    def test_fk_options_int_drops_relation_over_its_own_limit(self):
        # Cardinality (3 distinct names) exceeds the per-relation limit (2):
        # nothing is emitted, and the target keeps out of the shared block.
        for n in ('Dune', 'Solaris', 'It'):
            self._book(n)

        class IntSchema(DjangoQLSchema):
            fk_options = {Book: {'similar_books': 2}}

        bundle = describe_schema_for_llm(IntSchema(Book), max_fk_options=0)
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
        self.assertNotIn('core.book', bundle['dictionaries'])


class CompactFormatTest(TestCase):
    def _bundle(self):
        return describe_schema_for_llm(DjangoQLSchema(Book), format='compact')

    def test_compact_returns_a_string(self):
        self.assertIsInstance(self._bundle(), str)

    def test_header_lists_operators_once(self):
        text = self._bundle()
        # operator hints live in the header, not on every field line
        self.assertIn('Operators', text)
        self.assertIn('start model: core.book', text)

    def test_scalar_line_has_no_operator_tokens(self):
        text = self._bundle()
        line = next(
            ln
            for ln in text.splitlines()
            if ln.strip().startswith('is_published')
        )
        self.assertIn('bool', line)
        # a plain bool line must not spell out operators
        self.assertNotIn('!=', line)

    def test_nullable_marked_with_question_mark(self):
        text = self._bundle()
        line = next(
            ln
            for ln in text.splitlines()
            if ln.strip().startswith('published_date')
        )
        self.assertIn('date?', line)

    def test_relation_rendered_with_arrow(self):
        text = self._bundle()
        line = next(
            ln for ln in text.splitlines() if ln.strip().startswith('author')
        )
        self.assertIn('-> auth.user', line)

    def test_choice_field_lists_choices(self):
        text = self._bundle()
        line = next(
            ln for ln in text.splitlines() if ln.strip().startswith('genre')
        )
        self.assertIn('choices:', line)
        self.assertIn('Drama', line)

    def test_relation_references_dictionary_block(self):
        Book.objects.create(
            name='Dune',
            author=User.objects.create(username='ada'),
        )
        Book.objects.create(
            name='Solaris',
            author=User.objects.create(username='alan'),
        )
        text = describe_schema_for_llm(DjangoQLSchema(Book), format='compact')
        line = next(
            ln
            for ln in text.splitlines()
            if ln.strip().startswith('similar_books')
        )
        # The relation names its dictionary key; values live in the shared
        # block, not inline on the line.
        self.assertIn('-> core.book', line)
        self.assertIn('match name', line)
        self.assertNotIn('"Dune"', line)
        # ...but the value appears exactly once, in the dictionaries block.
        self.assertEqual(1, text.count('"Dune"'))

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            describe_schema_for_llm(DjangoQLSchema(Book), format='yaml')

    def test_nullable_relation_marked_with_question_mark(self):
        text = self._bundle()
        line = next(
            ln
            for ln in text.splitlines()
            if ln.strip().startswith('content_type')
        )
        # content_type is a nullable FK -> the arrow target carries ?
        self.assertIn('-> contenttypes.contenttype?', line)

    def test_object_reference_keeps_its_values(self):
        User.objects.create(username='ada')
        User.objects.create(username='alan')
        text = describe_schema_for_llm(
            AuthorPickerSchema(Book),
            format='compact',
        )
        line = next(
            ln for ln in text.splitlines() if ln.strip().startswith('author')
        )
        self.assertIn('object_reference', line)
        self.assertIn('ada', line)

    def test_multi_field_match_renders_each_field(self):
        User.objects.create(username='ada', email='ada@x.io')

        class ListSchema(DjangoQLSchema):
            fk_options = {Book: {'author': ['username', 'email']}}

        text = describe_schema_for_llm(ListSchema(Book), format='compact')
        line = next(
            ln for ln in text.splitlines() if ln.strip().startswith('author')
        )
        # Both match fields are named on the relation line; their values are
        # listed once in the shared dictionaries block.
        self.assertIn('match username, email', line)
        self.assertIn('username: ', text)
        self.assertIn('email: ', text)

    def test_compact_relation_line_includes_label_and_help_text(self):
        from djangoql.llm import _compact_field

        facts = {
            'type': 'relation',
            'nullable': False,
            'relates_to': 'auth.user',
            'label': 'Author',
            'help_text': 'Who wrote it',
        }
        line = _compact_field('author', facts, 6)
        self.assertIn('Author', line)
        self.assertIn('Who wrote it', line)

    def test_compact_nullable_object_reference(self):
        from djangoql.llm import _compact_field

        facts = {'type': 'str', 'nullable': True, 'object_reference': True}
        line = _compact_field('picker', facts, 6)
        self.assertIn('# str? (object_reference)', line)


class NoValueTargetsTest(TestCase):
    """``schema.no_value_targets``: a hard denylist of relation-target models
    whose row values must NEVER be emitted, regardless of ``fk_options`` or
    ``max_fk_options``. Stronger than the auto-only sensitive-target guard.
    """

    def _book(self, name):
        author = User.objects.create(username='u-%s' % name)
        return Book.objects.create(name=name, author=author)

    def test_control_without_denylist_similar_books_auto_emits(self):
        # Baseline: similar_books -> Book is small/non-sensitive, so auto mode
        # normally surfaces values (once, in dictionaries). The denylist tests
        # below suppress it.
        for n in ('Dune', 'Solaris'):
            self._book(n)
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        similar = bundle['models']['core.book']['similar_books']
        self.assertIn('match_field', similar)
        self.assertIn('core.book', bundle['dictionaries'])

    def test_model_class_target_suppresses_related_values(self):
        for n in ('Dune', 'Solaris'):
            self._book(n)

        class Schema(DjangoQLSchema):
            no_value_targets = (Book,)

        bundle = describe_schema_for_llm(Schema(Book))
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
        self.assertNotIn('core.book', bundle['dictionaries'])

    def test_dotted_label_target_suppresses_related_values(self):
        for n in ('Dune', 'Solaris'):
            self._book(n)

        class Schema(DjangoQLSchema):
            no_value_targets = ('core.Book',)

        bundle = describe_schema_for_llm(Schema(Book))
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
        self.assertNotIn('core.book', bundle['dictionaries'])

    def test_denylist_overrides_explicit_fk_options_true(self):
        # fk_options=True normally forces emission and overrides even the
        # sensitive-target guard; no_value_targets must still win.
        for n in ('Dune', 'Solaris'):
            self._book(n)

        class Schema(DjangoQLSchema):
            fk_options = {Book: {'similar_books': True}}
            no_value_targets = (Book,)

        bundle = describe_schema_for_llm(Schema(Book))
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
        self.assertNotIn('core.book', bundle['dictionaries'])

    def test_bad_label_is_ignored_not_fatal(self):
        # A misspelled/absent label must not break schema description.
        for n in ('Dune', 'Solaris'):
            self._book(n)

        class Schema(DjangoQLSchema):
            no_value_targets = ('core.NoSuchModel',)

        bundle = describe_schema_for_llm(Schema(Book))
        similar = bundle['models']['core.book']['similar_books']
        # unknown target -> no suppression, auto emission intact
        self.assertIn('match_field', similar)
        self.assertIn('core.book', bundle['dictionaries'])


class DictionaryDedupTest(TestCase):
    """A related model's values are emitted ONCE, in a top-level
    ``dictionaries`` block, and every relation to that model *references* them
    by ``(relates_to, match_field)`` instead of inlining a fresh copy.

    ``core.book`` is targeted by three relations (``similar_books`` forward,
    plus the reverse ``book`` on ``auth.user`` and ``contenttypes.contenttype``)
    -- so a naive per-FK emitter repeats the same name list three times.
    """

    def _book(self, name):
        author = User.objects.create(username='u-%s' % name)
        return Book.objects.create(name=name, author=author)

    def test_compact_emits_shared_values_exactly_once(self):
        for n in ('Dune', 'Solaris', 'It'):
            self._book(n)
        text = describe_schema_for_llm(DjangoQLSchema(Book), format='compact')
        # Three relations point at core.book, but its name list appears once.
        self.assertEqual(1, text.count('"Dune"'))
        self.assertEqual(1, text.count('"Solaris"'))

    def test_compact_relations_reference_dictionary_not_inline(self):
        for n in ('Dune', 'Solaris'):
            self._book(n)
        text = describe_schema_for_llm(DjangoQLSchema(Book), format='compact')
        # The old inline `match <field> in (...)` per FK is gone.
        self.assertNotIn('match name in (', text)
        # The similar_books relation line references core.book, without values.
        line = next(
            ln
            for ln in text.splitlines()
            if ln.strip().startswith('similar_books')
        )
        self.assertIn('-> core.book', line)
        self.assertNotIn('"Dune"', line)

    def test_compact_has_a_dictionaries_section(self):
        for n in ('Dune', 'Solaris'):
            self._book(n)
        text = describe_schema_for_llm(DjangoQLSchema(Book), format='compact')
        self.assertIn('dictionaries', text)
        self.assertIn('core.book', text)

    def test_json_dictionaries_block_holds_values_once(self):
        for n in ('Dune', 'Solaris', 'It'):
            self._book(n)
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        self.assertIn('dictionaries', bundle)
        self.assertEqual(
            {'Dune', 'Solaris', 'It'},
            set(bundle['dictionaries']['core.book']['name']),
        )

    def test_json_relation_carries_match_field_not_values(self):
        for n in ('Dune', 'Solaris'):
            self._book(n)
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        similar = bundle['models']['core.book']['similar_books']
        self.assertEqual('name', similar['match_field'])
        self.assertNotIn('related_values', similar)

    def test_json_no_field_anywhere_carries_related_values(self):
        for n in ('Dune', 'Solaris'):
            self._book(n)
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        for fields in bundle['models'].values():
            for facts in fields.values():
                if isinstance(facts, dict):
                    self.assertNotIn('related_values', facts)
                    self.assertNotIn('related_examples', facts)

    def test_all_relations_to_same_model_share_one_entry(self):
        for n in ('Dune', 'Solaris'):
            self._book(n)
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        # core.book has exactly one match key ('name'), shared by all three
        # relations that point at it.
        self.assertEqual(['name'], list(bundle['dictionaries']['core.book']))
        similar = bundle['models']['core.book']['similar_books']
        reverse_from_user = bundle['models']['auth.user']['book']
        self.assertEqual('name', similar['match_field'])
        self.assertEqual('name', reverse_from_user['match_field'])

    def test_different_match_fields_to_same_model_are_separate_entries(self):
        from django.contrib.auth.models import Permission

        User.objects.create(username='ada', email='ada@x.io')

        class Schema(DjangoQLSchema):
            fk_options = {
                Book: {'author': 'username'},
                Permission: {'user': 'email'},
            }

        bundle = describe_schema_for_llm(Schema(Book))
        user_dict = bundle['dictionaries']['auth.user']
        self.assertEqual(['ada'], user_dict['username'])
        self.assertEqual(['ada@x.io'], user_dict['email'])
        self.assertEqual(
            'username',
            bundle['models']['core.book']['author']['match_field'],
        )
        self.assertEqual(
            'email',
            bundle['models']['auth.permission']['user']['match_field'],
        )

    def test_str_examples_land_in_dictionary_under_str_key(self):
        User.objects.create(username='ada')

        class Schema(DjangoQLSchema):
            fk_options = {Book: {'author': '__str__'}}

        bundle = describe_schema_for_llm(Schema(Book))
        author = bundle['models']['core.book']['author']
        self.assertEqual('__str__', author['match_field'])
        self.assertEqual(
            ['ada'], bundle['dictionaries']['auth.user']['__str__']
        )

    def test_max_fk_options_zero_yields_no_dictionaries(self):
        self._book('Dune')
        bundle = describe_schema_for_llm(DjangoQLSchema(Book), max_fk_options=0)
        self.assertEqual({}, bundle['dictionaries'])
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)

    def test_sensitive_target_stays_out_of_dictionaries(self):
        self._book('Dune')
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        # author -> auth.User is sensitive: never auto-dumped, not even the
        # password field, and no auth.user entry in the shared dictionaries.
        self.assertNotIn('auth.user', bundle['dictionaries'])
        author = bundle['models']['core.book']['author']
        self.assertNotIn('match_field', author)
        self.assertNotIn('password', json.dumps(bundle))

    def test_no_value_targets_keeps_model_out_of_dictionaries(self):
        for n in ('Dune', 'Solaris'):
            self._book(n)

        class Schema(DjangoQLSchema):
            fk_options = {Book: {'similar_books': True}}
            no_value_targets = (Book,)

        bundle = describe_schema_for_llm(Schema(Book))
        self.assertNotIn('core.book', bundle['dictionaries'])
        similar = bundle['models']['core.book']['similar_books']
        self.assertNotIn('match_field', similar)
