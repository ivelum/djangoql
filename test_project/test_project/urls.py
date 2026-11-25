"""test_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from core.admin import zaibatsu_admin_site
from core.views import completion_demo, user_autocomplete


urlpatterns = [
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^zaibatsu-admin/', zaibatsu_admin_site.urls),
    path(
        'autocomplete/user/',
        user_autocomplete,
        name='user-autocomplete',
    ),
    path('', completion_demo),
]

if settings.DEBUG and settings.DJDT:
    import debug_toolbar

    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
