/*
 * Admin glue for the opt-in highlighting overlay (DjangoQLSearchMixin
 * .djangoql_highlight = True).
 *
 * The admin search textarea is created dynamically by completion_admin.js, so
 * we attach the overlay from a DOMReady callback registered after it (the
 * textarea therefore already exists). Outside the admin, use the generic
 * `textarea.djangoql-highlight` auto-init or DjangoQLHighlight.attachOverlay().
 */
(function (DjangoQL, Highlight) {
  'use strict';
  if (!DjangoQL || !Highlight) {
    return;
  }
  DjangoQL.DOMReady(function () {
    var textarea = document.querySelector('textarea[name=q]');
    if (textarea) {
      textarea.classList.add('djangoql-highlight');
      Highlight.attachOverlay(textarea);
    }
  });
}(window.DjangoQL, window.DjangoQLHighlight));
