from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import python_2_unicode_compatible


def get_favorite_query_name():
    count = FavoriteQuery.objects.count() + 1

    return 'Query %s' % count


@python_2_unicode_compatible
class FavoriteQuery(models.Model):
    """
    A favorite query model.
    """

    PRIVATE = 'private'
    SHARED = 'shared'
    SCOPE_CHOICES = (
        (PRIVATE, _('Private')),
        (SHARED, _('Shared')),
    )
    name = models.TextField(
        verbose_name=_('Name'),
        blank=True,
        default=get_favorite_query_name,
    )
    text = models.TextField(
        verbose_name=_('Query text'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('User'),
        related_name='favorite_query_list',
    )
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        verbose_name=_('Content Type'),
        related_name='favorite_query_list',
        on_delete=models.CASCADE,
    )
    scope = models.CharField(
        verbose_name=_('Scope'),
        max_length=10,
        choices=SCOPE_CHOICES,
        default=PRIVATE,
    )

    class Meta:
        verbose_name = _('Favorite query')
        verbose_name_plural = _('Favorite queries')
        unique_together = ('text', 'content_type', 'user',)
        ordering = ['-pk']

    def __str__(self):
        return self.text

    def as_dict(self, user):
        # primitive serializer

        return {
            'pk': self.pk,
            'text': self.text,
            'name': self.name,
            'scope': self.scope,
            'is_editable': user == self.user
        }
