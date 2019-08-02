(function (SavedQueries, DjangoQL) {
  'use strict';

  function getModelFromUrl() {
    var parts = location.href.split('/');
    return parts[parts.length - 2];
  }

  DjangoQL.DOMReady(function () {
    SavedQueries.init({
      view: new SavedQueries.View({
        inputSelector: 'textarea[name=q]',
        formSelector: '#changelist-search',
        submitSelector: '[type="submit"]',
        queryIdInputSelector: 'input[name=q-id]',
        buttonText: 'Saved queries'
      }),
      repo: new SavedQueries.QueryRepo({
        endpoint: '/djangoql/query/',
        model: getModelFromUrl()
      }),
      submitOnSelect: true
    });
  });
}(window.SavedQueries, window.DjangoQL));
