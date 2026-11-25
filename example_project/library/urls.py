from django.urls import path

from . import views


urlpatterns = [
    path('', views.index, name='demo'),
    path('syntax-help/', views.syntax_help, name='demo-syntax-help'),
    path('api/format/', views.api_format, name='demo-api-format'),
    path('api/explain/', views.api_explain, name='demo-api-explain'),
    path('api/search/', views.api_search, name='demo-api-search'),
]
