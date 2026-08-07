"""Standalone (non-admin) showcase views.

These call the DjangoQL primitives directly — ``apply_search`` (run a query),
``format_query`` (pretty-print), and ``explain`` (per-branch counts) — to show
that the features work outside the admin too. The query box on these pages uses
the library's own front-end primitives (multiline.js, highlight.js) with a
custom palette; styling here is deliberately "turned up" — it is a demo.

The API endpoints are ``csrf_exempt`` purely to keep this self-contained demo
simple. Do not copy that into a real project.
"""

import json
import re

from django.core.exceptions import FieldError, ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import translation
from django.views.decorators.csrf import csrf_exempt

from djangoql.breakdown import explain
from djangoql.exceptions import DjangoQLError
from djangoql.formatter import format_query
from djangoql.queryset import apply_search
from djangoql.serializers import DjangoQLSchemaSerializer
from djangoql.syntax_help import (
    AVAILABLE_LANGUAGES,
    render_syntax_help,
    resolve_language,
)

from .models import Book
from .schema import BookSchema


QUERY_ERRORS = (DjangoQLError, ValueError, FieldError, ValidationError)

EXAMPLES = [
    'rating > 4.5 and in_stock = True',
    'author.country.name = "Poland" or publisher.name ~ "Press"',
    'year >= 2000 and (genres.name = "Science Fiction" or rating > 4)',
    'pages > 400 and author.alive = True and price < 30',
    'rating > 4 and rating < 2',
    'author.name = = "x"',
]


def index(request):
    # Introspections power the completion widget (field/value auto-completion).
    # Embedded inline so the page needs no extra request.
    introspections = DjangoQLSchemaSerializer().serialize(BookSchema(Book))
    return render(
        request,
        'library/demo.html',
        {
            'examples': EXAMPLES,
            'introspections': json.dumps(introspections),
        },
    )


def syntax_help(request):
    """Render the DjangoQL syntax help as HTML, outside the admin.

    Because this project installs ``markdown`` (see requirements.txt), the same
    ``render_syntax_help`` helper that the admin uses compiles the per-language
    Markdown to HTML here. A ``?lang=`` query parameter lets a visitor preview
    any of the bundled translations without configuring LocaleMiddleware — handy
    for a demo; a real site would let language follow the request instead.
    """
    requested = request.GET.get('lang') or translation.get_language()
    language = resolve_language(requested)
    body, is_html = render_syntax_help(
        language, static('djangoql/img/completion_example.png')
    )
    return render(
        request,
        'library/syntax_help.html',
        {
            'body': body,
            'is_html': is_html,
            'language': language,
            'languages': sorted(AVAILABLE_LANGUAGES),
        },
    )


def _query(request):
    if request.method == 'POST':
        return request.POST.get('q', '')
    return request.GET.get('q', '')


def _locate(query, needle):
    """1-based (line, column) of ``needle`` in ``query``, or (None, None).

    A word-boundary match is preferred so ``rating`` doesn't match inside
    ``ratings``; falls back to a plain substring search.
    """
    match = re.search(r'(?<![\w.])' + re.escape(needle) + r'(?![\w])', query)
    pos = match.start() if match else query.find(needle)
    if pos < 0:
        return None, None
    line = query.count('\n', 0, pos) + 1
    # rfind == -1 (no newline before) yields a 1-based column of pos + 1.
    column = pos - query.rfind('\n', 0, pos)
    return line, column


def _error_response(exc, query=''):
    """JSON error with a 1-based (line, column) so the front-end can mark the
    spot in the query box.

    Parse/lex errors carry the position directly. Schema errors (e.g. "unknown
    field") don't, but they carry the offending name, which we locate in the
    query. ``mark`` tells the front-end whether to flag just that token
    (``"token"``) or the whole broken tail from there (``"to_end"``, default).
    """
    payload = {'error': str(exc)}
    line = getattr(exc, 'line', None)
    column = getattr(exc, 'column', None)
    mark = 'to_end'
    if not (line and column):
        value = getattr(exc, 'value', None)
        # str() so booleans/numbers locate too ("True", "5"); skip None/empty.
        needle = '' if value is None else str(value)
        if needle:
            line, column = _locate(query, needle)
            mark = 'token'
    if line and column:
        payload['line'] = line
        payload['column'] = column
        payload['mark'] = mark
    return JsonResponse(payload, status=400)


@csrf_exempt
def api_format(request):
    query = _query(request)
    if not query.strip():
        return JsonResponse({'formatted': ''})
    try:
        return JsonResponse({'formatted': format_query(query)})
    except DjangoQLError as e:
        return _error_response(e, query)


@csrf_exempt
def api_explain(request):
    query = _query(request)
    if not query.strip():
        return JsonResponse({'tree': None})
    try:
        tree = explain(Book.objects.all(), query, BookSchema)
    except QUERY_ERRORS as e:
        return _error_response(e, query)
    return JsonResponse({'tree': tree})


@csrf_exempt
def api_search(request):
    query = _query(request)
    qs = Book.objects.all().select_related('author', 'publisher')
    if query.strip():
        try:
            qs = apply_search(qs, query, BookSchema)
        except QUERY_ERRORS as e:
            return _error_response(e, query)
    total = qs.count()
    rows = [
        {
            'title': b.title,
            'author': b.author.name,
            'publisher': b.publisher.name if b.publisher else '',
            'year': b.year,
            'rating': b.rating,
            'price': str(b.price),
            'in_stock': b.in_stock,
        }
        for b in qs[:100]
    ]
    return JsonResponse({'total': total, 'shown': len(rows), 'rows': rows})
