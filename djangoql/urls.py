from djangoql.views import QueryView
from django.conf.urls import url, include


app_name = 'djangoql'
urlpatterns = [
    url(
        r'^query/(?P<pk>\d+)$',
        QueryView.as_view(),
        name='concrete_query'
    ),
    url(
        r'^query/',
        QueryView.as_view(),
        name='query'
    )
]
