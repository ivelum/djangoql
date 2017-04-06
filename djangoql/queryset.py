from django.db.models import Q, QuerySet

from .ast import Logical
from .parser import DjangoQLParser
from .schema import DjangoQLSchema


def build_filter(expr):
    if isinstance(expr.operator, Logical):
        left, right = Q(build_filter(expr.left)), Q(build_filter(expr.right))
        if expr.operator.operator == 'or':
            return left | right
        else:
            return left & right
    search = '__'.join(expr.left.parts)
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
    return ~q if invert else q


def apply_search(queryset, search, schema=None):
    """
    Applies search written in DjangoQL mini-language to given queryset
    """
    ast = DjangoQLParser().parse(search)
    schema = schema or DjangoQLSchema
    schema(queryset.model).validate(ast)
    return queryset.filter(build_filter(ast))


class DjangoQLQuerySet(QuerySet):
    djangoql_schema = None

    def djangoql(self, search, schema=None):
        return apply_search(self, search, schema=schema or self.djangoql_schema)
