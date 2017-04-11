from django.db.models import Q, QuerySet

from .ast import Logical
from .parser import DjangoQLParser
from .schema import DjangoQLSchema


def build_filter(expr, schema, queryset):
    if isinstance(expr.operator, Logical):
        left, queryset = build_filter(expr.left, schema, queryset)
        right, queryset = build_filter(expr.right, schema, queryset)
        if expr.operator.operator == 'or':
            return Q(left) | Q(right), queryset
        else:
            return Q(left) & Q(right), queryset
    search = '__'.join(expr.left.parts)
    field = schema.path_to_field(
        expr.left.parts
    )
    if field:
        queryset = field.add_search_target(queryset)

    invert = False
    op = {
        '=': '',
        '>': '__gt',
        '>=': '__gte',
        '<': '__lt',
        '<=': '__lte',
        '~': '__icontains',
        'in': '__in',
    }.get(expr.operator.operator)
    if op is None:
        op = {
            '!=': '',
            '!~': '__icontains',
            'not in': '__in',
        }[expr.operator.operator]
        invert = True
    q = Q(**{'%s%s' % (search, op): expr.right.value})
    return ~q if invert else q, queryset


def apply_search(queryset, search, schema=None):
    """
    Applies search written in DjangoQL mini-language to given queryset
    """
    ast = DjangoQLParser().parse(search)
    schema = schema or DjangoQLSchema
    schema = schema(queryset.model)
    schema.validate(ast)
    filters, queryset = build_filter(ast, schema, queryset)
    return queryset.filter(filters)


class DjangoQLQuerySet(QuerySet):
    djangoql_schema = None

    def djangoql(self, search, schema=None):
        return apply_search(self, search, schema=schema or self.djangoql_schema)
