import json

from django.contrib.auth.models import Group, User
from django.shortcuts import render_to_response
from django.views.decorators.http import require_GET

from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema


class UserQLSchema(DjangoQLSchema):
    include = (User, Group)


@require_GET
def completion_demo(request):
    q = request.GET.get('q', '')
    error = ''
    base_query = User.objects.all()
    try:
        search_results = apply_search(base_query, q, schema=UserQLSchema)
    except DjangoQLError as e:
        search_results = base_query.none()
        error = str(e)
    return render_to_response('completion_demo.html', {
        'q': q,
        'error': error,
        'search_results': search_results,
        'introspections': json.dumps(UserQLSchema(base_query.model).as_dict()),
    })
