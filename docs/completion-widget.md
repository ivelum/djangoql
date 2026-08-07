# Using completion widget outside of Django admin

The completion widget is not tightly coupled to Django admin, so you can easily use it outside of the admin if you want. The widget is [available on npm](https://www.npmjs.com/package/djangoql-completion) as a standalone package. See the source code and the docs in the [djangoql-completion](https://github.com/ivelum/djangoql-completion) repo on GitHub.

The completion widget is also bundled with the [djangoql-iplweb](https://pypi.org/project/djangoql-iplweb/) Python package on PyPI. If you're not using Webpack or another JavaScript bundler, you can use the pre-built version that ships with the Python package. Here is an example:

Template code, `completion_demo.html`:

``` html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>DjangoQL completion demo</title>
  <link rel="stylesheet" type="text/css" href="{% static 'djangoql/css/completion.css' %}" />
  <script src="{% static 'djangoql/js/completion.js' %}"></script>
</head>
<body>

  <form action="" method="get">
    <p style="color: red">{{ error }}</p>
    <textarea name="q" cols="40" rows="1" autofocus>{{ q }}</textarea>
  </form>

  <ul>
  {% for item in search_results %}
    <li>{{ item }}</li>
  {% endfor %}
  </ul>

  <script>
    DjangoQL.DOMReady(function () {
      new DjangoQL({
        // either JS object with a result of DjangoQLSchema(MyModel).as_dict(),
        // or an URL from which this information could be loaded asynchronously
        introspections: {{ introspections|safe }},

        // css selector for query input or HTMLElement object.
        // It should be a textarea
        selector: 'textarea[name=q]',

        // optional, you can provide URL for Syntax Help link here.
        // If not specified, Syntax Help link will be hidden.
        syntaxHelp: null,

        // optional, enable textarea auto-resize feature. If enabled,
        // textarea will automatically grow its height when entered text
        // doesn't fit, and shrink back when text is removed. The purpose
        // of this is to see full search query without scrolling, could be
        // helpful for really long queries.
        autoResize: true
      });
    });
  </script>
</body>
</html>
```

And in your `views.py`:

``` python
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
    return render(request, 'completion_demo.html', {
        'q': q,
        'error': error,
        'search_results': query,
        'introspections': json.dumps(introspections),
    })
```
