var django;
(function($) {
  "use strict";
  var URL = 'query/';

  // from django docs https://docs.djangoproject.com/en/1.8/ref/csrf/
  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var i,
        cookie,
        cookies = document.cookie.split(';');
      for (i = 0; i < cookies.length; i++) {
        cookie = $.trim(cookies[i]);
        // Does this cookie string begin with the name we want?
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  $(function () {
    $.ajaxSetup({
      headers: {'X-CSRFToken': getCookie('csrftoken')}
    });

    $('#searchbar')
        .wrap('<div class="djangoql-query-area"></div>')
        .parent()
        .prepend('' +
          '<div class="query-name-bar">' +
          '    <a href="#" id="edit-name" class="changelink">' +
          '      Query name' +
          '    </a>' +
          '    <input type="text" id="query-name" placeholder="Enter query name">' +
          '</div>')
        .prepend('<label for="query-public">Public: </label><input type="checkbox" id="query-public" title="Public">')
        .append('<a id="save-query" class="addlink icon" href="#" title="Save query"></a>')
        .append('<a id="view-queries" class="viewlink icon" href="#" title="View queries"></a>')
        .append('' +
          '<div class="search-queries">' +
          '    <div>' +
          '        <input type="search" placeholder="Search by name or by query" id="find-query-input">' +
          '    </div>' +
          '    <div>' +
          '        <ul id="query-list">' +
          '            ' +
          '        </ul>' +
          '    </div>' +
          '</div>'
        );
  });
})(django.jQuery);
