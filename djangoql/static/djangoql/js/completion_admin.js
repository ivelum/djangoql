(function (DjangoQL, helpers) {
  'use strict';

  // Replace standard search input with textarea and add completion toggle
  DjangoQL.DOMReady(function () {
    // use '-' in the param name to prevent conflicts with any model field name
    var QLParamName = 'q-l';
    var QLEnabled = helpers.parseQueryString()[QLParamName] === 'on';
    var QLInput;
    var QLToggle;
    var QLPlaceholder = 'Advanced search with Query Language';
    var originalPlaceholder;
    var textarea;
    var input = document.querySelector('input[name=q]');
    var djangoQL;

    if (!input) {
      return;
    }
    originalPlaceholder = input.placeholder;

    function onCompletionToggle(e) {
      if (e.target.checked) {
        djangoQL.enableCompletion();
        QLInput.name = QLParamName;
        textarea.placeholder = QLPlaceholder;
        textarea.focus();
        djangoQL.popupCompletion();
      } else {
        djangoQL.disableCompletion();
        QLInput.name = '';
        textarea.placeholder = originalPlaceholder;
        textarea.focus();
      }
    }

    if (DjangoQL._enableToggle) {
      QLInput = document.querySelector('input[name=' + QLParamName + ']');
      if (!QLInput) {
        QLInput = document.createElement('input');
        QLInput.type = 'hidden';
        input.parentNode.insertBefore(QLInput, input);
      }
      QLInput.name = QLEnabled ? QLParamName : '';
      QLInput.value = 'on';

      QLToggle = document.createElement('input');
      QLToggle.type = 'checkbox';
      QLToggle.checked = QLEnabled;
      QLToggle.className = 'djangoql-toggle';
      QLToggle.title = QLPlaceholder;
      QLToggle.onchange = onCompletionToggle;
      input.parentNode.insertBefore(QLToggle, input);
    } else {
      QLEnabled = true;
    }

    textarea = document.createElement('textarea');
    textarea.value = input.value;
    textarea.id = input.id;
    textarea.name = input.name;
    textarea.rows = 1;
    textarea.placeholder = QLEnabled ? QLPlaceholder : originalPlaceholder;
    textarea.setAttribute('maxlength', 2000);
    input.parentNode.insertBefore(textarea, input);

    input.parentNode.removeChild(input);
    textarea.focus();

    djangoQL = new DjangoQL({
      completionEnabled: QLEnabled,
      introspections: 'introspect/',
      syntaxHelp: 'djangoql-syntax/',
      selector: 'textarea[name=q]',
      autoResize: true
    });
  });
}(window.DjangoQL, window.DjangoQLHelpers));
