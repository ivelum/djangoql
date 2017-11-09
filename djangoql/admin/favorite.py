from django.conf.urls import url

from djangoql import views


class DjangoQLFavoriteQueryMixin(object):

    @property
    def media(self):
        media = super(DjangoQLFavoriteQueryMixin, self).media

        media.add_js((
            'djangoql/js/favorite.js',
        ))

        media.add_css({
            '': (
                'djangoql/css/favorite.css',
            ),
        })

        return media

    def get_urls(self):
        custom_urls = []

        custom_urls += [
            url(
                r'^favorite_queries/$',
                self.admin_site.admin_view(views.FavoriteQueryCreateListView.as_view(
                    model=self.model,
                )),
                name='%s_%s_create_list_favorite_queries' % (
                    self.model._meta.app_label,
                    self.model._meta.model_name,
                ),
            ),
            url(
                r'^favorite_queries/(?P<pk>\d+)/$',
                self.admin_site.admin_view(views.FavoriteQueryDestroyUpdateView.as_view()),
                name='%s_%s_destroy_update_favorite_queries' % (
                    self.model._meta.app_label,
                    self.model._meta.model_name,
                ),
            )
        ]

        return custom_urls + super(DjangoQLFavoriteQueryMixin, self).get_urls()
