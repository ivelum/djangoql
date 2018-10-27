(function (DjangoQL) {
  'use strict';

  function parseQueryString() {
    var qs = window.location.search.substring(1);
    var result = {};
    var vars = qs.split('&');
    var i;
    var l = vars.length;
    var pair;
    var key;
    for (i = 0; i < l; i++) {
      pair = vars[i].split('=');
      key = decodeURIComponent(pair[0]);
      if (key) {
        if (typeof result[key] !== 'undefined') {
          if (({}).toString.call(result[key]) !== '[object Array]') {
            result[key] = [result[key]];
          }
          result[key].push(decodeURIComponent(pair[1]));
        } else {
          result[key] = decodeURIComponent(pair[1]);
        }
      }
    }
    return result;
  }

  function parseQueryString() {
    var qs = window.location.search.substring(1);
    var result = {};
    var vars = qs.split('&');
    var i;
    var l = vars.length;
    var pair;
    var key;
    for (i = 0; i < l; i++) {
      pair = vars[i].split('=');
      key = decodeURIComponent(pair[0]);
      if (key) {
        if (typeof result[key] !== 'undefined') {
          if (({}).toString.call(result[key]) !== '[object Array]') {
            result[key] = [result[key]];
          }
          result[key].push(decodeURIComponent(pair[1]));
        } else {
          result[key] = decodeURIComponent(pair[1]);
        }
      }
    }
    return result;
  }

  // Replace standard search input with textarea and add completion toggle
  DjangoQL.DOMReady(function () {
    // use '-' in the param name to prevent conflicts with any model field name
    var QLParamName = 'q-l';
    var QLEnabled = parseQueryString()[QLParamName] === 'on';
    var QLInput;
    var QLToggle;
    var QLPlaceholder = 'Advanced search with Query Language';
    var originalPlaceholder;
    var textarea;
    var datalist;
    var input = document.querySelector('input[name=q]');

    if (!input) {
      return;
    }
    originalPlaceholder = input.placeholder;

    function onCompletionToggle(e) {
      if (e.target.checked) {
        DjangoQL.enableCompletion();
        QLInput.name = QLParamName;
        textarea.placeholder = QLPlaceholder;
        textarea.focus();
        DjangoQL.popupCompletion();
      } else {
        DjangoQL.disableCompletion();
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

    DjangoQL.init({
      completionEnabled: QLEnabled,
      introspections: 'introspect/',
      syntaxHelp: 'djangoql-syntax/',
      history: 'djangoql-history/',
      selector: 'textarea[name=q]',
      autoResize: true
    });
  });
}(window.DjangoQL));
