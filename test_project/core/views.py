import json

from django.contrib.auth.models import Group, User
from django.shortcuts import render
from django.views.decorators.http import require_GET

from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema
from djangoql.serializers import DjangoQLSchemaSerializer


class UserQLSchema(DjangoQLSchema):
    include = (User, Group)
    suggest_options = {
        Group: ['name'],
    }


@require_GET
def completion_demo(request):
    q = request.GET.get('q', '')
    error = ''
    query = User.objects.all().order_by('username')
    if q:
        try:
            query = apply_search(query, q, schema=UserQLSchema)
        except DjangoQLError as e:
            query = query.none()
            error = str(e)
    # You may want to use SuggestionsAPISerializer and an additional API
    # endpoint (see in djangoql.views) for asynchronous suggestions loading
    introspections = DjangoQLSchemaSerializer().serialize(
        UserQLSchema(query.model),
    )
    return render(request, 'completion_demo.html', context={
        'q': q,
        'error': error,
        'search_results': query,
        'introspections': json.dumps(introspections),
    })
