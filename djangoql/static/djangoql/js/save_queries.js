var django;
(function($) {
  "use strict";
  var URL = 'query/';

  var State = {
    queries: {},
    currentQuery: {
      query: '',
      name: '',
      public: false
    },
    update: function (data) {
      $.each(data, (function (key, value) {
        this.currentQuery[key] = value;
      }).bind(this));

    },
    choose: function (queryId) {
      var query = this.queries[queryId];
      this.currentQuery = $.extend({}, query);
      SearchFormComponent.choose(this.currentQuery);
    },
    save: function () {
      return $.post(URL, this.currentQuery)
        .success((function (data) {
          this.queries[data.id] = $.extend({}, this.currentQuery);
          QueryListComponent.append(this.queries[data.id]);
          SearchFormComponent.errorMessage.clean();
        }).bind(this))
        .fail(function (data) {
          SearchFormComponent.errorMessage.clean();
          SearchFormComponent.errorMessage.add(data.responseJSON.errors);
        });
    },
    deleteQuery: function (queryId) {
      return $.ajax({
          type: 'DELETE',
          url: URL + queryId,
          dataType: "json"
        })
        .then(
          (function () {
            delete this.queries[queryId];
            QueryListComponent.remove(queryId);
          }).bind(this)
        );
    },
    get: function () {
      return $.getJSON('query/').then(
        (function (data) {
          this.queries = {};
          $.each(data.value, (function (i, query) {
            this.queries[query.id] = query;
            QueryListComponent.append(query);
          }).bind(this));
        }).bind(this)
      );
    }
  };

  var QueryListComponent = {
    clean: function () {
      $('#query-list').html('');
    },
    remove: function (queryId) {
      $('#query-element-' + queryId).remove();
    },
    append: function (query) {
      var queryElement = $('#query-list')
        .append(
          '<li data-id="' + query.id + '" id="query-element-' + query.id + '" class="query-list-element">' +
          '    <a href="#" class="query-element">' +
          '      <h3><div class="query-name"></div></h3>' +
          '      <b><div class="query-body"></div></b>' +
          '    </a>' +
          '    <a href="#" class="delete-query deletelink"></a>' +
          '</li>'
        )
        .find('#query-element-' + query.id);
      queryElement.find('.query-name').text(query.name);
      queryElement.find('.query-body').text(query.query);
    },
    filter: function (searchStr) {
      $('.query-element').each(function () {
        var element = $(this);
        if (
          element.find('.query-name').text().indexOf(searchStr) !== -1 ||
          element.find('.query-body').text().indexOf(searchStr) !== -1
        ) {
          element.show();
        } else {
          element.hide();
        }
      });
    },
    toggle: function () {
      var queriesListElement = $('.search-queries');
      if(queriesListElement.is(":visible")) {
        setTimeout(function () {$(document).off('click', QueryListComponent.hideOnClick);}, 0);
      } else {
        setTimeout(function () {$(document).on('click', QueryListComponent.hideOnClick);}, 0);
      }
      queriesListElement.slideToggle();
    },
    hideOnClick: function (e) {
      if(!$(e.target).closest('.search-queries').length) {
        $('.search-queries').hide();
        $(document).off('click', QueryListComponent.hideOnClick );
      }
    }
  };

  var SearchFormComponent = {
    choose: function (query) {
      var textArea = $('#searchbar');
      $('#edit-name').text(query.name);
      $('#query-name').val(query.name);
      // resize to default height
      // TODO remove hardcode
      textArea.css('height', '19px');
      textArea.val(query.query).focus();
      textArea.css('height', (textArea.height() + textArea.scrollTop()) + 'px');
      QueryListComponent.toggle();
      this.hideNameInput();
    },
    errorMessage: {
      add: function (errMessages) {
        var errorTemplate = '' +
          '<div class="query-error {{ className }}">' +
          '    <b>{{ errMessage }}</b>' +
          '</div>';
        if ('name' in errMessages) {
          SearchFormComponent.showNameInput();
          $('#name-error-wrap').append(
            errorTemplate
              .replace('{{ className }}', 'query-name-error')
              .replace('{{ errMessage }}', errMessages.name.join(', '))
          );
        }
        if ('query' in errMessages) {
          $('#query-error-wrap').parent().append(
            errorTemplate
              .replace('{{ className }}', 'query-body-error')
              .replace('{{ errMessage }}', errMessages.query.join(', '))
          );
        }
      },
      clean: function() {
        $('.query-error').remove();
      }
    },
    showNameInput: function () {
      $('#edit-name').hide();
      $('#query-name').show();
    },
    hideNameInput: function () {
      $('#query-name').hide();
      $('#edit-name').show();
    },
    render: function () {
      var djangoqlQueryArea = $('#searchbar')
        .wrap('<div class="djangoql-query-area"></div>')
        .parent();
      djangoqlQueryArea
        .prepend(
          '<div class="query-name-bar">' +
          '    <a href="#" id="edit-name" class="changelink">' +
          '      Query name' +
          '    </a>' +
          '    <input type="text" id="query-name" placeholder="Enter query name">' +
          '</div>' +
          '<div id="name-error-wrap"></div>'
        )
        .prepend('<label for="query-public">Public: </label><input type="checkbox" id="query-public" title="Public">')
        .append('<a id="save-query" class="addlink icon" href="#" title="Save query"></a>')
        .append('<a id="view-queries" class="viewlink icon" href="#" title="View queries"></a>')
        .append(
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
        )
        .parent().append('<div id="query-error-wrap"></div>');
    }
  };

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

  function dynamicBindEvent(selector, event, handler) {
    /*
    To bind event on dynamically created elements prior then 1.17 the recommended approach was to use live(),
    however, live() was deprecated in 1.7 in favour of on(), and completely removed in 1.9
    */
    var versionStr = $.fn.jquery,
      versionParts = $.map(versionStr.split('.'), parseInt),
      majorVersion = versionParts[0],
      minorVersion = versionParts[1];
    if (majorVersion > 1 || minorVersion > 17) {
      $(document).on(event, selector, handler);
    } else {
      $(selector).live(event, handler);
    }
  }

  $(function () {
    $.ajaxSetup({
      headers: {'X-CSRFToken': getCookie('csrftoken')}
    });

    State.get();
    SearchFormComponent.render();

    dynamicBindEvent('.query-element', 'click', function (e) {
      e.preventDefault();
      var queryId = $(this).parent().data('id');
      State.choose(queryId);
    });

    dynamicBindEvent('.delete-query', 'click', function (e) {
      e.preventDefault();
      var queryId = $(this).parent().data('id');
      State.deleteQuery(queryId);
    });

    $('#find-query-input').on('change keyup paste', function () {
      var searchStr = $.trim($('#find-query-input').val());
      QueryListComponent.filter(searchStr);
    });

    dynamicBindEvent('#searchbar', 'change keyup paste focusout', function () {
      State.update({
        query: $.trim($('#searchbar').val())
      });
    });

    $('#edit-name').click(function (e) {
      e.preventDefault();
      SearchFormComponent.showNameInput();
      $('#query-name').focus();
    });

    $('#query-name')
      .on('change keyup paste', function () {
        var value = $.trim($('#query-name').val());
        State.update({name: value});
        $('#edit-name').text(value);
      })
      .focusout(function () {
        SearchFormComponent.hideNameInput();
      });

    $('#query-public').change(function () {
      State.update({public: this.checked});
    });

    $('#save-query').click(function (e) {
      e.preventDefault();
      State.save();
    });

    $('#view-queries').click(function (e) {
      e.preventDefault();
      QueryListComponent.toggle();
    });

  });
})(django.jQuery);
