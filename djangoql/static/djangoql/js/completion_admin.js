(function (DjangoQL) {
    'use strict';

    DjangoQL.DOMReady(function () {
        // Replace standard search input with textarea
        var textarea,
            queryArea,
            saveButton,
            viewButton,
            queryTitleBar;
        var input = document.querySelector('input[name=q]');
        if (!input) {
            return;
        }
        queryArea = document.createElement('div');
        queryArea.className += 'djangoql-query-area';
        saveButton = document.createElement('a');
        viewButton = document.createElement('a');
        queryTitleBar = document.createElement('div');

        saveButton.id = 'save-query';
        viewButton.id = 'view-queries';
        saveButton.className += 'icon icon_save';
        viewButton.className += 'icon icon_view';
        saveButton.setAttribute('href', '#');
        viewButton.setAttribute('href', '#');
        queryTitleBar.id = 'query-name';


        textarea = document.createElement('textarea');
        textarea.value = input.value;
        textarea.id = input.id;
        textarea.name = input.name;
        textarea.rows = 1;
        textarea.setAttribute('maxlength', 2000);

        queryArea.appendChild(textarea);
        queryArea.appendChild(saveButton);
        queryArea.appendChild(viewButton);
        // insert before surrounding div elemen
        input.parentNode.parentNode.insertBefore(queryTitleBar, input.parentNode);
        input.parentNode.insertBefore(queryArea, input);
        input.parentNode.removeChild(input);
        textarea.focus();

        DjangoQL.init({
            introspections: 'introspect/',
            syntaxHelp: 'djangoql-syntax/',
            selector: 'textarea[name=q]',
            autoResize: true
        });
    });
}(window.DjangoQL));
