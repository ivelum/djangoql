from unittest import TestCase

from djangoql.views import SuggestionsAPIView


class SuggestionsAPIViewTest(TestCase):
    def test_get_field_requires_schema(self):
        # Without a schema configured the view can't resolve any field.
        view = SuggestionsAPIView()
        with self.assertRaises(ValueError) as ctx:
            view.get_field('whatever')
        self.assertEqual('DjangoQL schema is undefined', str(ctx.exception))
