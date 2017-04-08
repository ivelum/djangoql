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
    query = User.objects.all().order_by('username')
    if q:
        try:
            query = apply_search(query, q, schema=UserQLSchema)
        except DjangoQLError as e:
            query = query.none()
            error = str(e)
    return render_to_response('completion_demo.html', {
        'q': q,
        'error': error,
        'search_results': query,
        'introspections': json.dumps(UserQLSchema(query.model).as_dict()),
    })
