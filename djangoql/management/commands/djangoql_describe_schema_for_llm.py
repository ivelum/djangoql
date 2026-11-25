"""``djangoql_describe_schema_for_llm`` -- dump a model's DjangoQL search space
as JSON.

The output is an LLM-ready description of everything that can be queried against
a model: fields, types, relations, allowed operators, plus a grammar
cheat-sheet and examples. Feed it into a prompt to teach an LLM to generate
valid DjangoQL for that model.

Examples::

    python manage.py djangoql_describe_schema_for_llm library.Book
    python manage.py djangoql_describe_schema_for_llm library.Book \
        --schema library.schema.BookSchema
    python manage.py djangoql_describe_schema_for_llm library.Book \
        --indent 0 > book_schema.json
"""

import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils.module_loading import import_string

from djangoql.llm import describe_schema_for_llm
from djangoql.schema import DjangoQLSchema


class Command(BaseCommand):
    help = (
        "Describe a model's DjangoQL search space as JSON (fields, types, "
        'relations, operators and examples), ready for an LLM prompt.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'model',
            help='Model to describe, as "app_label.ModelName" '
            '(e.g. library.Book).',
        )
        parser.add_argument(
            '--schema',
            dest='schema',
            default=None,
            help='Dotted path to a DjangoQLSchema subclass to use instead of '
            'the default (e.g. library.schema.BookSchema). Use this to '
            'mirror the schema your admin/view actually exposes.',
        )
        parser.add_argument(
            '--indent',
            type=int,
            default=2,
            help='JSON indentation (default: 2). Use 0 for the most compact '
            'multi-line output.',
        )
        parser.add_argument(
            '--max-fk-options',
            type=int,
            default=50,
            help='Max distinct related-model values to embed per relation '
            '(default: 50). 0 disables automatic relation values; explicit '
            'fk_options on the schema still apply.',
        )
        parser.add_argument(
            '--format',
            dest='format',
            choices=['json', 'compact'],
            default='json',
            help='Output format: json (default, machine-readable) or compact '
            '(terse text, smallest for large schemas).',
        )

    def handle(self, *args, **options):
        model = self._resolve_model(options['model'])
        schema_cls = self._resolve_schema(options['schema'])
        try:
            schema = schema_cls(model)
        except Exception as e:
            raise CommandError(
                'Could not build %s for %s: %s'
                % (schema_cls.__name__, options['model'], e),
            )
        fmt = options['format']
        bundle = describe_schema_for_llm(
            schema,
            format=fmt,
            max_fk_options=options['max_fk_options'],
        )
        if fmt == 'compact':
            self.stdout.write(bundle)
        else:
            indent = options['indent'] or None
            self.stdout.write(
                json.dumps(
                    bundle,
                    indent=indent,
                    ensure_ascii=False,
                    default=str,
                ),
            )

    def _resolve_model(self, label):
        try:
            app_label, model_name = label.split('.')
        except ValueError:
            raise CommandError(
                'Model must be given as "app_label.ModelName", got %r.' % label,
            )
        try:
            return apps.get_model(app_label, model_name)
        except (LookupError, ValueError) as e:
            raise CommandError(f'Unknown model {label!r}: {e}')

    def _resolve_schema(self, dotted_path):
        if not dotted_path:
            return DjangoQLSchema
        try:
            schema_cls = import_string(dotted_path)
        except ImportError as e:
            raise CommandError(
                f'Could not import schema {dotted_path!r}: {e}',
            )
        if not (
            isinstance(schema_cls, type)
            and issubclass(schema_cls, DjangoQLSchema)
        ):
            raise CommandError(
                '%r is not a DjangoQLSchema subclass.' % dotted_path,
            )
        return schema_cls
