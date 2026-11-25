import json

from django.contrib import messages
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import FieldError, ValidationError
from django.db import DataError, NotSupportedError
from django.forms import Media
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import path, reverse
from django.utils.translation import get_language
from django.views.i18n import JavaScriptCatalog

from .breakdown import explain, explain_empty
from .exceptions import DjangoQLError
from .formatter import format_query
from .queryset import apply_search
from .schema import DjangoQLSchema
from .serializers import SuggestionsAPISerializer
from .syntax_help import (
    get_syntax_help_title,
    render_syntax_help,
    resolve_language,
)
from .views import SuggestionsAPIView


DJANGOQL_SEARCH_MARKER = 'q-l'


class DjangoQLChangeList(ChangeList):
    def get_filters_params(self, *args, **kwargs):
        params = super().get_filters_params(*args, **kwargs)
        if DJANGOQL_SEARCH_MARKER in params:
            del params[DJANGOQL_SEARCH_MARKER]
        return params


class DjangoQLSearchMixin:
    search_fields = ('_djangoql',)  # just a stub to have search input displayed
    djangoql_completion = True
    djangoql_completion_enabled_by_default = True
    djangoql_schema = DjangoQLSchema
    djangoql_syntax_help_template = 'djangoql/syntax_help.html'
    # Opt-in syntax highlighting overlay for the search box. Off by default:
    # the admin does not need it, and an overlay can interfere with the
    # completion widget's layout, so enabling it is a deliberate choice. When
    # on, the highlight.js/.css primitives are loaded and the search textarea
    # gets the ``djangoql-highlight`` class. Colours come from CSS variables and
    # are overridable; the library imposes no palette.
    djangoql_highlight = False
    # When a valid DjangoQL search returns zero rows, explain *where* in the
    # query the data runs out and surface it as a warning. Set to False to
    # disable the extra (lazy, count()-per-node) queries.
    djangoql_explain_empty = True
    # Cost guard for the empty-result breakdown: max AST nodes counted before
    # the breakdown is truncated to the top-level conjuncts.
    djangoql_explain_empty_max_nodes = 50

    def search_mode_toggle_enabled(self):
        # If search fields were defined on a child ModelAdmin instance,
        # we suppose that the developer wants two search modes and therefore
        # enable search mode toggle
        return self.search_fields != DjangoQLSearchMixin.search_fields

    def djangoql_search_enabled(self, request):
        return request.GET.get(DJANGOQL_SEARCH_MARKER, '').lower() == 'on'

    def get_changelist(self, *args, **kwargs):
        return DjangoQLChangeList

    def get_search_results(self, request, queryset, search_term):
        if (
            self.search_mode_toggle_enabled()
            and not self.djangoql_search_enabled(request)
        ):
            return super().get_search_results(
                request=request,
                queryset=queryset,
                search_term=search_term,
            )
        use_distinct = False
        if not search_term:
            return queryset, use_distinct

        try:
            qs = apply_search(queryset, search_term, self.djangoql_schema)
        except (DjangoQLError, ValueError, FieldError, ValidationError) as e:
            msg = self.djangoql_error_message(e)
            messages.add_message(request, messages.WARNING, msg)
            qs = queryset.none()
        else:
            # Hack to handle 'inet' comparison errors in Postgres. If you
            # know a better way to check for such an error, please submit a PR.
            try:
                # Django >= 2.1 has built-in .explain() method
                explain = getattr(qs, 'explain', None)
                if callable(explain):
                    try:
                        explain()
                    except NotSupportedError:
                        list(qs[:1])
                else:
                    list(qs[:1])
            except DataError as e:
                if 'inet' not in str(e):
                    raise
                msg = self.djangoql_error_message(e)
                messages.add_message(request, messages.WARNING, msg)
                qs = queryset.none()
            else:
                self.djangoql_add_empty_breakdown(
                    request,
                    queryset,
                    qs,
                    search_term,
                )

        return qs, use_distinct

    def djangoql_add_empty_breakdown(self, request, queryset, qs, search_term):
        """If a valid DjangoQL search returned zero rows, compute and surface
        a breakdown of *where* the query runs out of data as a warning.

        Lazy: this is only attempted when ``djangoql_explain_empty`` is on and
        the result set is empty, so the extra count() queries never run on a
        non-empty search.
        """
        if not self.djangoql_explain_empty:
            return
        exists = getattr(qs, 'exists', None)
        # Only real querysets support a cheap emptiness check; anything else
        # (e.g. a test double) is left untouched.
        if not callable(exists) or exists():
            return
        try:
            breakdown = explain_empty(
                queryset,
                search_term,
                self.djangoql_schema,
                max_nodes=self.djangoql_explain_empty_max_nodes,
            )
        except (DjangoQLError, ValueError, FieldError, ValidationError):
            # Never let the breakdown break the changelist; it's a best-effort
            # diagnostic on top of an already-empty result.
            return
        if breakdown is None:
            return
        msg = render_to_string(
            'djangoql/empty_breakdown.html',
            context={'node': breakdown},
        )
        messages.add_message(request, messages.WARNING, msg)

    def djangoql_error_message(self, exception):
        if isinstance(exception, ValidationError):
            msg = exception.messages[0]
        else:
            msg = str(exception)
        return render_to_string(
            'djangoql/error_message.html',
            context={
                'error_message': msg,
                'djangoql_syntax_help_url': reverse(
                    '%s:djangoql_syntax_help' % self.admin_site.name,
                ),
            },
        )

    @property
    def media(self):
        media = super().media
        if self.djangoql_completion:
            js = [
                # The djangojs gettext catalog, served as a view (root-relative
                # URL). It must come first so window.gettext is defined before
                # completion.js localises the operator hints / placeholder.
                reverse(
                    '{}:{}_{}_djangoql_i18n'.format(
                        self.admin_site.name,
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    )
                ),
                'djangoql/js/completion.js',
            ]
            if self.search_mode_toggle_enabled():
                js.append('djangoql/js/completion_admin_toggle.js')
                if not self.djangoql_completion_enabled_by_default:
                    js.append('djangoql/js/completion_admin_toggle_off.js')
            js.append('djangoql/js/completion_admin.js')
            # Shift+Enter -> newline (Enter still submits). Loaded last so the
            # admin textarea created by completion_admin.js already exists; the
            # script itself is framework-agnostic and delegates on document.
            js.append('djangoql/js/multiline.js')
            css = [
                'djangoql/css/completion.css',
                'djangoql/css/completion_admin.css',
            ]
            if self.djangoql_highlight:
                # Opt-in highlighting overlay (see djangoql_highlight).
                js.append('djangoql/js/highlight.js')
                js.append('djangoql/js/completion_admin_highlight.js')
                css.append('djangoql/css/highlight.css')
            media += Media(css={'': tuple(css)}, js=js)
        return media

    def get_urls(self):
        custom_urls = []
        if self.djangoql_completion:
            custom_urls += [
                path(
                    'introspect/',
                    self.admin_site.admin_view(self.introspect),
                    name='{}_{}_djangoql_introspect'.format(
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    ),
                ),
                path(
                    'suggestions/',
                    self.admin_site.admin_view(self.suggestions),
                    name='{}_{}_djangoql_suggestions'.format(
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    ),
                ),
                path(
                    'format/',
                    self.admin_site.admin_view(self.djangoql_format),
                    name='{}_{}_djangoql_format'.format(
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    ),
                ),
                path(
                    'explain/',
                    self.admin_site.admin_view(self.djangoql_explain),
                    name='{}_{}_djangoql_explain'.format(
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    ),
                ),
                path(
                    'djangoql-i18n/',
                    self.admin_site.admin_view(
                        JavaScriptCatalog.as_view(packages=['djangoql']),
                        cacheable=True,
                    ),
                    name='{}_{}_djangoql_i18n'.format(
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    ),
                ),
                path(
                    'djangoql-syntax/',
                    self.admin_site.admin_view(self.djangoql_syntax_help),
                    name='djangoql_syntax_help',
                ),
            ]
        return custom_urls + super().get_urls()

    def djangoql_syntax_help(self, request):
        """Render the syntax help page for the active language.

        The help text is authored as per-language Markdown (see
        :mod:`djangoql.syntax_help`). It is compiled to HTML when a Markdown
        library is importable, and otherwise served as raw Markdown inside a
        ``<pre>`` block — djangoql does not depend on a Markdown compiler. The
        surrounding page chrome comes from ``djangoql_syntax_help_template``,
        which integrators may override.
        """
        requested_language = (
            request.GET.get('lang')
            or request.GET.get('language')
            or getattr(request, 'LANGUAGE_CODE', None)
            or get_language()
        )
        language = resolve_language(requested_language)
        body, is_html = render_syntax_help(
            language,
            static('djangoql/img/completion_example.png'),
        )
        context = {
            **self.admin_site.each_context(request),
            'title': get_syntax_help_title(language),
            'body': body,
            'is_html': is_html,
            'language': language,
        }
        return render(request, self.djangoql_syntax_help_template, context)

    def djangoql_format(self, request):
        """Pretty-print a query and return it as JSON.

        On-demand primitive backing a "Format" button: the front-end posts the
        raw query (``q``) and gets back ``{"formatted": ...}``. A query that
        does not parse yields ``{"error": ...}`` with HTTP 400. How (or whether)
        to wire a Format button into the UI is the integrator's decision.
        """
        query = request.POST.get('q', request.GET.get('q', ''))
        if not query.strip():
            return JsonResponse({'formatted': ''})
        try:
            formatted = format_query(query)
        except DjangoQLError as e:
            return JsonResponse({'error': str(e)}, status=400)
        return JsonResponse({'formatted': formatted})

    def djangoql_explain(self, request):
        """Return a per-node count breakdown of a query as JSON.

        On-demand primitive backing a "show counts / explain" action: the
        front-end posts the raw query (``q``) and gets back ``{"tree": …}`` —
        a tree of ``{text, count, role, children}`` with one ``count()`` per
        node. ``tree`` is ``null`` for an empty query; an invalid query yields
        ``{"error": …}`` with HTTP 400.

        This runs one ``count()`` per node, so it is deliberately *not* invoked
        automatically per search — the front-end calls it when the user asks.
        How (or whether) to surface it in the UI is the integrator's decision.
        """
        query = request.POST.get('q', request.GET.get('q', ''))
        if not query.strip():
            return JsonResponse({'tree': None})
        try:
            tree = explain(
                self.get_queryset(request),
                query,
                self.djangoql_schema,
                max_nodes=self.djangoql_explain_empty_max_nodes,
            )
        except (DjangoQLError, ValueError, FieldError, ValidationError) as e:
            return JsonResponse({'error': str(e)}, status=400)
        return JsonResponse({'tree': tree})

    def introspect(self, request):
        suggestions_url = reverse(
            '{}:{}_{}_djangoql_suggestions'.format(
                self.admin_site.name,
                self.model._meta.app_label,
                self.model._meta.model_name,
            )
        )
        serializer = SuggestionsAPISerializer(suggestions_url)
        response = serializer.serialize(self.djangoql_schema(self.model))
        return HttpResponse(
            content=json.dumps(response, indent=2),
            content_type='application/json; charset=utf-8',
        )

    def suggestions(self, request):
        view = SuggestionsAPIView.as_view(
            schema=self.djangoql_schema(self.model),
        )
        return view(request)
