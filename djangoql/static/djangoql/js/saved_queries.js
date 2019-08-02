/**
 * Saved queries module for DjangoQL plugin.
 *
 * Consists of three main components:
 * - QueryRepo - interacts with the backend
 * - View - abstracts DOM, sends interaction events to Controller
 * - Controller - wires up view and repo
 *
 * Module exposes View and QueryRepo as a constructors for external
 * instantiation (which can be used for substitution in unit tests),
 * and the "init" function that constructs Controller with provided view and
 * repo as parameters.
 */
(function (root, factory) {
  'use strict';

  /* global define, require */

  if (typeof define === 'function' && define.amd) {
    // AMD. Register as an anonymous module.
    define('SavedQueries', ['DjangoQLHelpers'], factory);
  } else if (typeof exports === 'object') {
    // Node. Does not work with strict CommonJS, but
    // only CommonJS-like environments that support module.exports,
    // like Node.
    module.exports = factory(require('DjangoQLHelpers'));  // eslint-disable-line
  } else {
    // Browser globals (root is window)
    root.SavedQueries = factory(root.DjangoQLHelpers);  // eslint-disable-line
  }
}(this, function (helpers) {
  var DJANGO_QL_QUERY_ID = 'q-id';
  var DJANGO_QUERY_PARAM = 'q';

  /**
   * Query repository. Persists and retrieves queries from a backend
   *
   * @constructor
   * @param {object} params
   * @param {string} params.endpoint - URL for requests
   * @param {string} params.model - Model name
   * @param {string} params.token - Django CSRF-token
   */
  function QueryRepo(params) {
    this.endpoint = params.endpoint;
    this.model = params.model;
    this.token = helpers.getCookie('csrftoken');
  }

  /**
   * Get query from repository
   *
   * @param {number} id
   * @param {function} [callback]
   */
  QueryRepo.prototype.get = function (id, callback) {
    var req = new XMLHttpRequest();
    req.open('GET', this.getUrl(id), true);
    req.onload = function () {
      if (req.status !== 200) {
        // eslint-disable-next-line no-console
        console.error(req.responseText);
      } else if (callback) {
        callback(JSON.parse(req.responseText));
      }
    };
    req.send();
  };

  /**
   * Save query
   *
   * @param {object} obj
   * @param {function} [callback]
   */
  QueryRepo.prototype.save = function (obj, callback) {
    var req = new XMLHttpRequest();
    req.open('POST', this.getUrl(), true);
    req.setRequestHeader('X-CSRFToken', this.token);
    req.setRequestHeader('Content-Type', 'application/json;charset=UTF-8');
    req.onload = function () {
      if (req.status !== 200) {
        // eslint-disable-next-line no-console
        console.error(req.responseText);
      } else if (callback) {
        callback(JSON.parse(req.responseText));
      }
    };
    req.send(JSON.stringify(obj));
  };

  /**
   * Get list of saved queries
   *
   * @param {function} [callback]
   */
  QueryRepo.prototype.list = function (callback) {
    var req = new XMLHttpRequest();
    req.open('GET', this.getUrl(), true);
    req.onload = function () {
      if (req.status !== 200) {
        // eslint-disable-next-line no-console
        console.error(req.responseText);
      } else if (callback) {
        callback(JSON.parse(req.responseText));
      }
    };
    req.send();
  };

  /**
   * Remove saved query
   *
   * @param {number} id
   * @param {function} [callback]
   */
  QueryRepo.prototype.remove = function (id, callback) {
    var req = new XMLHttpRequest();
    req.open('DELETE', this.getUrl(id), true);
    req.setRequestHeader('X-CSRFToken', this.token);
    req.onload = function () {
      if (req.status !== 200) {
        // eslint-disable-next-line no-console
        console.error(req.responseText);
      } else if (callback) {
        callback(JSON.parse(req.responseText));
      }
    };
    req.send();
  };

  /**
   * Get the url for requests
   *
   * @param {number} [id]
   * @returns {string}
   */
  QueryRepo.prototype.getUrl = function (id) {
    return this.endpoint + (id || '') + '?model=' + this.model;
  };

  /**
   * Controller for saved queries:
   * - retrieves and persists the model via the query repository
   * - exposes the model to the view and provides event handlers
   *
   * @param {object} params
   * @param {object} params.view - Instance of the View
   * @param {object} params.repo - Instance of the QueryRepository
   * @param {object} params.submitOnSelect - Submit form when query selected
   */
  function Controller(params) {
    this.view = params.view;
    this.repo = params.repo;
    this.submitOnSelect = params.submitOnSelect;
    this.currentQuery = null;

    this.initCurrentQuery();
    this.refreshQueryList();

    this.view.subscribe('selectQuery', this.selectQuery.bind(this));
    this.view.subscribe('removeQuery', this.removeQuery.bind(this));
    this.view.subscribe('changeQueryScope', this.changeQueryScope.bind(this));
    this.view.subscribe('saveAsNewQuery', this.saveAsNewQuery.bind(this));
    this.view.subscribe('renameQuery', this.renameQuery.bind(this));
    this.view.subscribe('resetCurrentQuery', this.resetCurrentQuery.bind(this));
    this.view.subscribe('saveAsCurrentQuery',
      this.saveAsCurrentQuery.bind(this));
  }

  /**
   * Removes query from repo
   *
   * @param {object} query
   * @param {function} callback
   */
  Controller.prototype.removeQuery = function (query, callback) {
    var self = this;
    var isCurrent = self.currentQuery && (query.id === self.currentQuery.id);
    this.repo.remove(query.id, function () {
      if (callback) {
        callback();
      }
      if (isCurrent) {
        self.resetCurrentQuery();
      }
    });
  };

  /**
   * Changes the private/public attribute of the query
   *
   * @param {object} query
   * @param {function} callback
   */
  Controller.prototype.changeQueryScope = function (query, callback) {
    this.repo.save({
      id: query.id,
      name: query.name,
      text: query.text,
      private: !query.private
    }, callback);
  };

  /**
   * If the current query is set - tell to the view about this
   */
  Controller.prototype.initCurrentQuery = function () {
    var qs = helpers.parseQueryString();
    var self = this;
    var currentQueryId = qs[DJANGO_QL_QUERY_ID];
    if (!currentQueryId) {
      // init without an object
      self.view.setCurrentQuery();
      return;
    }
    this.repo.get(currentQueryId, function (obj) {
      self.view.setCurrentQuery(obj);
      self.currentQuery = obj;
    });
  };

  /**
   * Select query:
   *  - set appropriate attributes to the url (query text and id)
   *  - reload the page if necessary
   *  - or just tell to view about the selected query
   *
   * @param {object} query
   * @param {boolean} noReload
   */
  Controller.prototype.selectQuery = function (query, noReload) {
    var loc;
    loc = window.location.href;
    loc = helpers.updateURLParameter(loc, DJANGO_QUERY_PARAM, query.text);
    loc = helpers.updateURLParameter(loc, DJANGO_QL_QUERY_ID, query.id);
    // Use the history API for url changes, since we don't always need to
    // reload the page when choosing a query
    history.replaceState(null, null, loc);
    if (this.submitOnSelect && !noReload) {
      location.reload();
      return;
    }
    this.currentQuery = query;
    this.view.setCurrentQuery(query);
  };

  /**
   * Reset current query:
   * - tell to the view about this
   * - update url params
   */
  Controller.prototype.resetCurrentQuery = function () {
    var location;
    this.currentQuery = null;
    this.view.setCurrentQuery();
    location = window.location.href;
    location = helpers.updateURLParameter(location, DJANGO_QL_QUERY_ID, null);
    // Use the history API for url changes, since we just resets current state,
    // but want to persist this state after the page is reloaded
    history.replaceState(null, null, location);
  };

  /**
   * Saves current search as new query
   *
   * @param {string} [name]
   * @param {function} [callback]
   */
  Controller.prototype.saveAsNewQuery = function (name, callback) {
    // eslint-disable-next-line no-alert
    var newName = name || prompt('Please enter a name for the new query');
    var text = this.view.getSearchText();
    var self = this;
    var query;
    if (!(newName && text)) {
      return;
    }
    query = { name: newName, text: text };
    this.repo.save(query, function (result) {
      if (callback) {
        callback(result);
      }
      self.selectQuery({ text: text, id: result.id, name: newName }, true);
      self.refreshQueryList();
    });
  };

  /**
   * Save current search as selected query
   *
   * @param {string} [name]
   * @param {function} callback
   */
  Controller.prototype.saveAsCurrentQuery = function (name, callback) {
    var self = this;
    this.repo.save({
      name: name || this.currentQuery.name,
      text: this.view.getSearchText(),
      id: this.currentQuery.id
    }, function () {
      self.refreshQueryList();
      if (callback) {
        callback();
      }
    });
  };

  /**
   * Renames current selected query.
   * if the name is not specified, ask the user to enter it
   *
   * @param {object} query
   * @param {number} query.id
   * @param {string} query.text
   * @param {boolean} query.private
   * @param {string} name
   * @param {function} callback
   */
  Controller.prototype.renameQuery = function (query, name, callback) {
    var self = this;
    var changed;
    // eslint-disable-next-line no-alert
    var newName = name || prompt(
      'Please enter a new name for the query', query.name);
    if (!newName) {
      return;
    }
    changed = {
      id: query.id,
      name: newName,
      text: query.text,
      private: query.private
    };
    this.repo.save(changed, function () {
      if (callback) {
        callback();
      }
      if (self.currentQuery && (query.id === self.currentQuery.id)) {
        self.view.setCurrentQuery(changed);
      }
      self.refreshQueryList();
    });
  };

  /**
   * Refreshes the query list from the repo
   */
  Controller.prototype.refreshQueryList = function () {
    var self = this;
    this.repo.list(function (data) {
      self.view.populateQueryList(data);
    });
  };

  /**
   * Base prototype for view components
   *
   * @constructor
   * @param {object} params
   * @param {object} params.eventBus
   */
  function ViewComponent(params) {
    this.eventBus = params && params.eventBus;
    this.element = this.buildElement();
    // Backref for debugging
    this.element.view = this;
  }

  /**
   * Factory method for building a DOM-element
   *
   * @returns {object} DOM-element
   */
  ViewComponent.prototype.buildElement = function () {
    // eslint-disable-next-line no-console
    console.error('Must override buildElement method in concrete component.');
  };

  /**
   * Inserts the element of the current component after the specified
   *
   * @param {object} ref DOM-element to insert after
   */
  ViewComponent.prototype.insertAfter = function (ref) {
    ref.parentNode.insertBefore(this.element, ref.nextSibling);
  };

  /**
   * Snaps the element of the current component to the specified
   *
   * @param {object} ref DOM-element
   */
  ViewComponent.prototype.snapTo = function (ref) {
    var rect1 = this.element.getBoundingClientRect();
    var rect2 = ref.getBoundingClientRect();

    /* eslint-disable no-param-reassign */
    this.element.style.top = (rect2.top + rect2.height +
      window.pageYOffset + 'px');
    this.element.style.left = ((rect2.left - rect1.width) +
      rect2.width + window.pageXOffset + 'px');
  };

  /**
   * Insert the current element to another
   *
   * @param {object} container
   */
  ViewComponent.prototype.insertInto = function (container) {
    container.appendChild(this.element);
  };

  /**
   * Toggle visibility of the current element
   *
   * @param {boolean} [val] visibility
   */
  ViewComponent.prototype.toggle = function (val) {
    var visibility = (val === undefined ? !this.isVisible() : val);
    this.element.style.display = visibility ? 'block' : 'none';
  };

  /**
   * Determines whether the element is visible or not
   *
   * @returns {boolean}
   */
  ViewComponent.prototype.isVisible = function () {
    return this.element.style.display !== 'none';
  };

  /**
   * Removes all element contents
   */
  ViewComponent.prototype.clean = function () {
    this.element.innerHTML = '';
  };

  /**
   * Set text to element
   *
   * @param {string} text
   */
  ViewComponent.prototype.setText = function (text) {
    this.element.innerText = text;
  };


  /**
   * Label to display current selected query
   */
  function QueryLabel() {
    ViewComponent.apply(this, arguments);
  }

  QueryLabel.prototype = Object.create(ViewComponent.prototype);

  /**
   * Builds label contents
   *
   * @returns {object}
   */
  QueryLabel.prototype.buildElement = function () {
    var self = this;
    var el = document.createElement('div');
    el.className = 'djangoql-sq-label';
    this.label = document.createElement('span');
    this.label.className = 'djangoql-sq-label-name';
    this.reset = document.createElement('span');
    this.reset.className = 'djangoql-sq-label-reset';
    el.appendChild(this.label);
    el.appendChild(this.reset);
    this.reset.addEventListener('click', function () {
      self.eventBus.notify('resetCurrentQuery');
    });
    this.eventBus.subscribe('setCurrentQuery', function (query) {
      if (query) {
        self.setText(query.name);
        self.toggle(true);
      } else {
        self.toggle(false);
      }
    });
    return el;
  };

  /**
   * Set text to label
   *
   * @param {string} text
   */
  QueryLabel.prototype.setText = function (val) {
    this.label.innerText = val;
  };

  /**
   * Button for displaying saved queries dialog
   *
   * @param {object} params
   * @param {string} params.buttonText
   */
  function Button(params) {
    this.buttonText = params.buttonText;

    ViewComponent.apply(this, arguments);
  }

  Button.prototype = Object.create(ViewComponent.prototype);

  /**
   * Builds button contents
   *
   * @returns {object}
   */
  Button.prototype.buildElement = function () {
    var el = document.createElement('input');
    el.type = 'submit';
    el.className = 'djangoql-sq-button';
    el.value = this.buttonText;
    return el;
  };

  /**
   * Actions in query dialog
   */
  function QueryActions() {
    var self = this;
    ViewComponent.apply(this, arguments);

    this.populate();

    // Show "save as new" only when search input is not empty
    this.eventBus.subscribe('searchTextChanged', function (val) {
      self.toggleAction('new', !!val);
    });
    // Show "save as ..." only when current query selected
    this.eventBus.subscribe('setCurrentQuery', function (query) {
      self.toggleAction('current', !!query);
      if (query) {
        self.getActionById('current').innerText = (
          'Save as "' + query.name + '"');
      }
    });
  }

  QueryActions.prototype = Object.create(ViewComponent.prototype);

  /**
   * Get action by identifier
   *
   * @param {string} id
   * @returns {object}
   */
  QueryActions.prototype.getActionById = function (id) {
    return this.element.querySelector('[data-id="' + id + '"]');
  };

  /**
   * Toggles visibility of the action
   *
   * @param {number} id
   * @param {boolean} val
   */
  QueryActions.prototype.toggleAction = function (id, val) {
    this.getActionById(id).style.display = val ? 'block' : 'none';
  };

  /**
   * Add default actions to the list
   */
  QueryActions.prototype.populate = function () {
    var self = this;

    this.addAction('Save as new query', 'new', function () {
      self.eventBus.notify('saveAsNewQuery');
    });

    this.addAction('', 'current', function () {
      self.eventBus.notify('saveAsCurrentQuery');
    });
  };

  /**
   * Builds container for query actions
   */
  QueryActions.prototype.buildElement = function () {
    var el = document.createElement('ul');
    el.className = 'djangoql-sq-actions';
    return el;
  };

  /**
   * Add query actions with provided parameters
   *
   * @param {string} name
   * @param {number} id
   * @param {function} callback
   */
  QueryActions.prototype.addAction = function (name, id, callback) {
    var action = document.createElement('li');
    action.innerText = name;
    action.title = name;
    action.style.display = 'none';
    action.dataset.id = id;
    action.addEventListener('click', callback);
    this.element.appendChild(action);
  };

  /**
   * List of saved queries
   */
  function QueryList() {
    ViewComponent.apply(this, arguments);

    this.placeholder = this.buildPlaceholder();
    this.element.appendChild(this.placeholder);
  }

  QueryList.prototype = Object.create(ViewComponent.prototype);

  /**
   * Builds container for the saved queries list
   */
  QueryList.prototype.buildElement = function () {
    var el = document.createElement('ul');
    el.className = 'django-sq-query-list';
    return el;
  };

  /**
   * Builds placeholder for an empty list
   */
  QueryList.prototype.buildPlaceholder = function () {
    var placeholder = document.createElement('li');
    placeholder.className = 'django-sq-query-list-placeholder';
    placeholder.innerText = 'Query list is empty';
    return placeholder;
  };

  /**
   * Populate query list with provided data
   *
   * @param {array} data
   */
  QueryList.prototype.populate = function (data) {
    this.clean();
    data.forEach(this.addQuery.bind(this));
    this.handlePlaceholder();
  };

  /**
   * Removes all queries from the list (ignoring the placeholder)
   */
  QueryList.prototype.clean = function () {
    var items = this.element.getElementsByClassName(
      'djangoql-sq-query-row');
    var i;
    for (i = items.length - 1; i >= 0; i--) {
      items[i].remove();
    }
  };

  /**
   * Build an action for the query row
   *
   * @param {object} params
   * @param {object} params.name - Name to display in the list
   * @param {object} params.event - Event name
   * @param {object} params.title - Title to show on a hover
   * @param {object} params.query
   * @param {object} params.callback
   */
  QueryList.prototype.buildAction = function (params) {
    var action = document.createElement('span');
    var self = this;
    var name = params.name;
    var event = params.event;
    var title = params.title;
    var query = params.query;
    var callback = params.callback;

    action.innerText = name;
    action.title = title;
    action.addEventListener('click', function (e) {
      self.eventBus.notify(event, query);
      if (callback) {
        callback.call(action);
      }
      e.stopPropagation();
      self.handlePlaceholder();
    });
    return action;
  };

  /**
   * Adds a query to the list
   *
   * @param {object} query
   */
  QueryList.prototype.addQuery = function (query) {
    var self = this;
    var row = document.createElement('li');
    var name = document.createElement('span');
    var ops = document.createElement('span');

    this.element.appendChild(row);

    row.className = 'djangoql-sq-query-row';
    name.className = 'djangoql-sq-query-name';
    name.innerText = query.name;
    name.title = query.name;
    row.appendChild(name);
    ops.className = 'djangoql-sq-ops';
    row.appendChild(ops);

    ops.appendChild(
      this.buildAction({
        name: 'remove',
        event: 'removeQuery',
        title: 'Remove query',
        query: query,
        callback: row.parentNode.removeChild.bind(row.parentNode, row)
      }));

    ops.appendChild(
      this.buildAction({
        name: 'rename',
        event: 'renameQuery',
        title: 'Rename query',
        query: query
      }));

    ops.appendChild(
      this.buildAction({
        name: query.private ? 'private' : 'public',
        event: 'changeQueryScope',
        title: 'Change query scope',
        query: query,
        callback: function () {
          query.private = !query.private;
          this.innerHTML = query.private ? 'private' : 'public';
        }
      }));

    row.addEventListener('click', function () {
      self.eventBus.notify('selectQuery', query);
    });
  };

  /**
   * Shows a placeholder when there is no data
   */
  QueryList.prototype.handlePlaceholder = function () {
    this.placeholder.style.display = this.getQueryCount() ? 'none' : 'block';
  };

  /**
   * Returns the total queries count
   *
   * @returns {number}
   */
  QueryList.prototype.getQueryCount = function () {
    return this.element.getElementsByClassName(
      'djangoql-sq-query-row').length;
  };

  /**
   * Dialog with query actions and the query list
   */
  function Dialog() {
    ViewComponent.apply(this, arguments);

    this.queryList = new QueryList({ eventBus: this.eventBus });
    this.queryActions = new QueryActions({ eventBus: this.eventBus });
    this.element.appendChild(this.queryActions.element);
    this.element.appendChild(this.queryList.element);
    this.eventBus.subscribe('saveAsCurrentQuery',
      this.toggle.bind(this, false));
    this.eventBus.subscribe('saveAsNewQuery', this.toggle.bind(this, false));
  }

  Dialog.prototype = Object.create(ViewComponent.prototype);

  /**
   * Builds dialog contents
   *
   * @returns {object}
   */
  Dialog.prototype.buildElement = function () {
    var el = document.createElement('div');
    el.className = 'djangoql-sq-dialog';
    el.style.display = 'none';
    el.style.outline = 'none';
    el.tabIndex = 0;
    return el;
  };

  /**
   * Fill the query list with the provided data
   *
   * @param {array} data
   */
  Dialog.prototype.populateQueryList = function (data) {
    this.queryList.populate(data);
  };

  /**
   * Simple pub/sub implementation
   */
  function EventBus() {
    this.handlers = {};
  }

  /**
   * Subscribe a handler to provided event
   *
   * @param {string} event
   * @param {function} fn
   */
  EventBus.prototype.subscribe = function (event, fn) {
    this.handlers[event] = this.handlers[event] || [];
    this.handlers[event].push(fn);
  };

  /**
   * Unsubscribe a handler from the provided event
   *
   * @param {string} event
   * @param {function} fn
   */
  EventBus.prototype.unsubscribe = function (event, fn) {
    var handlers = this.handlers[event] || [];
    var position = handlers.indexOf(fn);
    if (position !== -1) {
      handlers.splice(position, 1);
    }
  };

  /**
   * Notify event subscribers
   *
   * @param {string} event
   * @param {object} payload
   */
  EventBus.prototype.notify = function (event, payload) {
    if (!this.handlers[event]) {
      return;
    }
    this.handlers[event].forEach(function (fn) {
      fn(payload);
    });
  };

  /**
   * Abstracts DOM elements for saved queries functionality
   *
   * @param {object} params
   * @param {object} params.formSelector
   * @param {object} params.submitSelector
   * @param {object} params.inputSelector
   * @param {object} params.queryIdInputSelector
   * @param {object} params.buttonText
   */
  function View(params) {
    var self = this;

    this.form = document.querySelector(params.formSelector);
    this.submit = this.form.querySelector(params.submitSelector);
    this.input = this.form.querySelector(params.inputSelector);
    if (params.queryIdInputSelector) {
      this.queryIdInput = this.form.querySelector(params.queryIdInputSelector);
    }

    // Event bus used to communicate with the controller
    this.eventBus = new EventBus();

    // Build components structure
    this.button = new Button({ eventBus: this.eventBus,
      buttonText: params.buttonText });
    this.button.insertAfter(this.submit);
    this.dialog = new Dialog({ eventBus: this.eventBus });
    this.dialog.insertInto(document.body);
    this.label = new QueryLabel({ eventBus: this.eventBus });
    this.label.insertInto(this.form);

    // Open/hide dialog on button click
    this.button.element.addEventListener('click', function (e) {
      e.preventDefault();
      self.dialog.toggle();
      self.dialog.snapTo(self.button.element);
      if (self.dialog.isVisible()) {
        self.dialog.element.focus();
      }
    });
    this.dialog.element.addEventListener('blur', function () {
      self.dialog.toggle(false);
    });

    this.eventBus.notify('searchTextChanged', this.input.value);
    this.eventBus.subscribe('selectQuery', function () {
      self.dialog.toggle(false);
    });
    this.input.addEventListener('change', function () {
      self.eventBus.notify('searchTextChanged', this.value);
    });
  }

  /**
   * Fills the query list with the provided data
   *
   * @param {array} data
   */
  View.prototype.populateQueryList = function (data) {
    this.dialog.populateQueryList(data);
  };

  /**
   * Subscribe to the view events
   *
   * @param {string} event
   * @param {function} fn
   */
  View.prototype.subscribe = function (event, fn) {
    return this.eventBus.subscribe(event, fn);
  };

  /**
   * Sets current query
   *
   * @param {object} query
   */
  View.prototype.setCurrentQuery = function (query) {
    this.currentQuery = query;
    this.eventBus.notify('setCurrentQuery', query);
    if (query) {
      this.input.value = query.text;
    } else if (this.queryIdInput) {
      this.queryIdInput.value = null;
    }
  };

  /**
   * Get search input contents
   *
   * @returns {string}
   */
  View.prototype.getSearchText = function () {
    return this.input.value;
  };

  /**
   * Set contents for search input
   *
   * @param {string} val
   */
  View.prototype.setSearchText = function (val) {
    this.input.value = val;
  };

  return {
    View: View,
    QueryRepo: QueryRepo,
    init: function (params) {
      return new Controller(params);
    }
  };
}));
