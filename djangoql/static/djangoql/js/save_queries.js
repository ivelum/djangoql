(function($) {
    "use strict";
    var formTemplate = '' +
      '<div class="save-query-form">\n' +
      '    <form id="save-query-form">\n' +
      '        <div>\n' +
      '            <label for="query-name">Name:</label>\n' +
      '            <input type="text" id="query-name" name="query_name">\n' +
      '        </div>\n' +
      '        <div>\n' +
      '            <label for="query-public">Public:</label>\n' +
      '            <input type="checkbox" id="query-public" name="query_public">\n' +
      '        </div>\n' +
      '        <div>\n' +
      '            <button type="submit">Save</button><button type="submit">Undo</button>\n' +
      '        </div>\n' +
      '    </form>\n' +
      '</div>\n',

      listTemplate = '' +
        '<div class="query-list">\n' +
        '    <div>\n' +
        '        <input type="search" placeholder="Find by name or query" id="find-query-input">\n' +
        '    </div>\n' +
        '    <div>\n' +
        '        <ul id="query-list">\n' +
        '            \n' +
        '        </ul>\n' +
        '    </div>\n' +
        '</div>',

      listElementTemplate = ''

      SavedQueryManager = {
          currentQuery: {
              query: '',
              name: ''
          },
          changed: function () {
              var currentValue = $('#searchbar').val().strip();
              return currentValue === this.currentQuery.query;
          },
          save: function () {

          },
          list: function () {
              $.getJSON('query/', function (data) {
                  var i,
                    queries = data.value;
                  for (i; i < queries.length; i++){
                      $('#query-list').append(

                      )
                  }
              });
          },
          choose: function (pk) {

          }
      };

    // from django docs https://docs.djangoproject.com/en/1.8/ref/csrf/
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = $.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) == (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    $(document).ready(function() {
        $.ajaxSetup({
            headers: { "X-CSRFToken": getCookie('csrftoken')}
        });

        $('#searchbar').change(function () {
            if (SavedQueryManager.changed()) {

            }
        });

        $('#save-query').click(function (e) {
            e.preventDefault();
            SavedQueryManager.saveQuery();
        });

        $('#view-queries').click(function (e) {
            e.preventDefault();
            SavedQueryManager.listQueries();
        });

    });

})(django.jQuery);
