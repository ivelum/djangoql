(function () {
  //  TODO ES6 syntax
  var searchBar;
  var searchForm;
  var table;
  var tableBody;
  var starButton;
  var listButton;
  var shiningStarIcon = '🌟';
  var starIcon = '⭐';
  var listIcon = '📖';
  var closeIcon = '❌';
  var trashIcon = '🗑️';
  var pencilIcon = '✏️';
  var successIcon = '✔️';
  var searchIcon = '🔎';
  var privateIcon = '🕵️';
  var sharedIcon = '👪';
  var pencilElementList = [];
  var trashElementList = [];
  var scopeElementList = [];
  var emptyClassName = 'djangoql-favorite__empty';

  /* Utils */
  function getChildsDataset(elem) {
    var result = [];

    if (elem.childNodes.length === 0) return [];

    elem.childNodes.forEach(function (item) {
      if (item.dataset !== undefined) {
        result.push(item.dataset.index);
      }
    });

    return result;
  }

  function getInputsForRow(row) {
    var inputs = row.querySelectorAll('input[type="text"]')
    var inputName = row.firstChild.firstChild;
    var inputText = row.firstChild.nextSibling.firstChild;

    return {
      inputName: inputName,
      inputText: inputText
    };
  }

  function insertAfter(elem, refElem) {
    return refElem.parentNode.insertBefore(elem, refElem.nextSibling);
  }

  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
  }

  function getURLEncodedBody(data) {
    var result = [];
    var parameter;
    var key;

    for (key in data) {
      if (data.hasOwnProperty(key)) {
        parameter = encodeURIComponent(key) + '=' +
          encodeURIComponent(data[key]);
        result.push(parameter);
      }
    }

    return result.join('&');
  }

  /* API interaction */
  function createFavoriteQuery(query) {
    var formData;

    starButton.textContent = shiningStarIcon;
    setTimeout(function () {
      starButton.textContent = starIcon;
    }, 500);

    formData = {
      text: query
    };

    return fetch('favorite_queries/', {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRFToken': getCookie('csrftoken')
      },
      credentials: 'same-origin',
      body: getURLEncodedBody(formData)
    }).then(function (response) {
      return response.json();
    });
  }

  function getFavoriteQueries() {
    return fetch('favorite_queries/', {
      method: 'GET',
      credentials: 'same-origin'
    }).then(function (response) {
      return response.json();
    });
  }

  function removeFavoriteQuery(parent) {
    return fetch('favorite_queries/' + parent.dataset.index + '/', {
      method: 'DELETE',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRFToken': getCookie('csrftoken')
      },
      credentials: 'same-origin'
    }).then(function (response) {
      return response.json();
    });
  }

  function updateFavoriteQuery(parent, formData) {
    return fetch('favorite_queries/' + parent.dataset.index + '/', {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-CSRFToken': getCookie('csrftoken')
      },
      credentials: 'same-origin',
      body: getURLEncodedBody(formData)
    }).then(function (response) {
      return response.json();
    });
  }

  /* Listeners */
  function listButtonListenerOnClick(event) {
    var target = event.target;

    table.style.top = listButton.getBoundingClientRect().top + 30 + 'px';
    table.style.left = listButton.getBoundingClientRect().left + 'px';

    if (target.classList.contains('visible')) {
      table.style.display = 'none';

      listButton.textContent = listIcon;
      listButton.setAttribute('title', 'Show favorite query list');
      listButton.classList.remove('visible');
    } else {
      table.style.display = 'block';

      listButton.textContent = closeIcon;
      listButton.setAttribute('title', 'Hide favorite query list');
      listButton.classList.add('visible');
    }
  }

  function documentListenerForListButtonOnClick(event) {
    var target = event.target;

    if (
      target === listButton ||
      target === starButton ||
      target === searchBar ||
      trashElementList.indexOf(target) > -1 ||
      pencilElementList.indexOf(target) > -1 ||
      scopeElementList.indexOf(target) > -1
    ) return;

    if (listButton.classList.contains('visible') === true) {
      table.style.display = 'none';

      listButton.textContent = listIcon;
      listButton.classList.remove('visible');
    }
  }

  function rowListenerOnMouseEnter(event) {
    var row = event.target;

    row.classList.add('active');
  }

  function rowListenerOnMouseLeave(event) {
    var row = event.target;

    row.classList.remove('active');
  }

  function searchListenerOnClick(event) {
    var search = event.target;
    var row = search.parentNode.parentNode;

    searchBar.value = row.dataset.text;
    searchForm.submit();
  }

  function trashListenerOnClick(event) {
    var trash = event.target;
    var search = trash.previousSibling; //
    var row = trash.parentNode.parentNode;

    removeFavoriteQuery(row).then(function (json) {
      if (json.favorite_query === null) {
        row.removeEventListener('mouseenter', rowListenerOnMouseEnter);
        row.removeEventListener('mouseleave', rowListenerOnMouseLeave);
        search.removeEventListener('click', searchListenerOnClick);
        trash.removeEventListener('click', trashListenerOnClick);

        row.parentNode.removeChild(row);

        if (tableBody.childNodes.length === 0) tableBody.appendChild(getEmptyRow());
      } else {
        alert(json.errors);
      }
    });
  }

  function scopeListenerOnClick() {
    var input = this.querySelector('input:checked');
    var scope = input.value;
    var formData = {
      scope: scope
    };

    if (input.disabled) return;

    updateFavoriteQuery(this.parentNode.parentNode, formData).then(function (json) {
      if (json.errors) {
        alert(json.errors);
        return;
      }
    });
  }

  function pencilListenerOnClick(event) {
    var target = event.target;
    var input = target.previousSibling;
    var inputs;
    var formData;
    var inputName;
    var inputText;
    var parent = this.parentNode.parentNode;

    input.selectionStart = input.selectionEnd = input.value.length;

    if (target.classList.contains('clicked')) {
      input.nextSibling.textContent = pencilIcon;
      input.nextSibling.classList.remove('clicked');
      inputs = getInputsForRow(input.parentNode.parentNode);

      inputName = inputs.inputName;
      inputText = inputs.inputText;

      formData = {
        name: inputName.value,
        text: inputText.value
      };

      updateFavoriteQuery(parent, formData).then(function (json) {
        if (json.errors) {
          alert(json.errors);
          return;
        }

        parent.dataset.name = json.favorite_query.name;
        parent.dataset.text = json.favorite_query.text;

        inputName.value = json.favorite_query.name;
        inputText.value = json.favorite_query.text;
      });
    } else {
      input.focus();
      input.nextSibling.textContent = successIcon;
      input.nextSibling.classList.add('clicked');
    }
  }

  function starButtonListenerOnClick() {
    var tableBodyDataset = getChildsDataset(tableBody);
    var query = searchBar.value;

    if (!query) return;

    if (tableBody.childNodes.length === 1 && tableBody.firstChild.className === emptyClassName) {
      tableBody.removeChild(tableBody.firstChild);
    }

    createFavoriteQuery(query).then(function (json) {
      if (tableBodyDataset.indexOf(json.favorite_query.pk.toString()) !== -1) return;
      tableBody.insertBefore(getFavoriteQueryRow(json.favorite_query), tableBody.firstChild);
    });
  }

  /* UI helpers */
  function getInputUI(value) {
    var input = document.createElement('input');

    input.value = value;
    input.className = 'djangoql-favorite__input';
    input.setAttribute('type', 'text');

    return input;
  }

  function getSearchUI() {
    var search;

    search = document.createElement('span');
    search.className = 'djangoql-favorite__search';
    search.textContent = searchIcon;
    search.setAttribute('title', 'Search');
    search.addEventListener('click', searchListenerOnClick);

    return search;
  }

  function getPencilUI() {
    var pencil;

    pencil = document.createElement('span');
    pencil.className = 'djangoql-favorite__pencil';
    pencil.textContent = pencilIcon;
    pencil.setAttribute('title', 'Edit');
    pencil.addEventListener('click', pencilListenerOnClick);
    pencilElementList.push(pencil);

    return pencil;
  }

  function getTrashUI() {
    var trash = document.createElement('span');

    trash.className = 'djangoql-favorite__trash';
    trash.textContent = trashIcon;
    trash.setAttribute('title', 'Remove query from favorite list');
    trash.addEventListener('click', trashListenerOnClick);
    trashElementList.push(trash);

    return trash;
  }

  function getScopeUI(item) {
    var scope = document.createElement('div');
    var privateInput = document.createElement('input');
    var privateLabel = document.createElement('label');
    var sharedInput = document.createElement('input');
    var sharedLabel = document.createElement('label');

    scope.className = 'djangoql-favorite__scope';
    scope.setAttribute('title', 'Set scope settings for query');

    privateInput.setAttribute('type', 'radio');
    privateInput.setAttribute('name', 'scope' + item.pk);
    privateInput.setAttribute('value', 'private');
    privateInput.setAttribute('title', 'Set private scope');
    privateLabel.textContent = privateIcon;
    scopeElementList.push(privateInput);

    sharedInput.setAttribute('type', 'radio');
    sharedInput.setAttribute('name', 'scope' + item.pk);
    sharedInput.setAttribute('value', 'shared');
    sharedInput.setAttribute('title', 'Set shared scope');
    sharedLabel.textContent = sharedIcon;
    scopeElementList.push(sharedInput);

    scope.appendChild(privateInput);
    scope.appendChild(privateLabel);
    scope.appendChild(sharedInput);
    scope.appendChild(sharedLabel);
    scope.addEventListener('click', scopeListenerOnClick);


    return scope;
  }

  function getRowUI(name, query, action, item) {
    var row;
    var trash;

    row = document.createElement('div');
    row.className = 'djangoql-favorite__row';

    name.className = 'djangoql-favorite__row-cell';
    query.className = 'djangoql-favorite__row-cell';
    action.className = 'djangoql-favorite__row-cell';

    row.appendChild(name);
    row.appendChild(query);
    row.appendChild(action);

    if (item) {
      row.dataset.index = item.pk;
      row.dataset.text = item.text;
      row.dataset.name = item.name;
      row.dataset.scope = item.scope;
      row.dataset.is_editable = item.is_editable;
      row.addEventListener('mouseenter', rowListenerOnMouseEnter);
      row.addEventListener('mouseleave', rowListenerOnMouseLeave);

      if (item.scope === 'private') {
        row.lastChild.getElementsByTagName('input')[0].checked = true;
      } else {
        row.lastChild.getElementsByTagName('input')[1].checked = true;
      }

      if (item.is_editable === false) {
        row.querySelectorAll('.djangoql-favorite__pencil').forEach(function (item) {
          item.removeEventListener('click', pencilListenerOnClick);
          item.parentNode.removeChild(item);
        });

        row.querySelectorAll('input[type="radio"]').forEach(function (item) {
          item.disabled = true;
        });

        trash = row.querySelector('.djangoql-favorite__trash');
        trash.removeEventListener('click', trashListenerOnClick);
        trash.parentNode.removeChild(trash);
      }
    }

    return row;
  }

  function getFavoriteQueryRow(item) {
    var name = document.createElement('div');
    var query = document.createElement('div');
    var action = document.createElement('div');
    var nameInput = getInputUI(item.name);
    var queryInput = getInputUI(item.text);

    name.appendChild(nameInput);
    name.appendChild(getPencilUI());

    query.appendChild(queryInput);
    query.appendChild(getPencilUI());

    action.appendChild(getSearchUI());
    action.appendChild(getScopeUI(item));
    action.appendChild(getTrashUI());

    return getRowUI(name, query, action, item);
  }

  function getEmptyRow() {
    var empty = document.createElement('div');

    empty.className = emptyClassName;
    empty.textContent = 'Favorite query list is empty';
    return empty;
  }

  function getTableHeader() {
    var header = document.createElement('div');
    var name = document.createElement('div');
    var query = document.createElement('div');
    var action = document.createElement('div');

    name.textContent = 'name';
    query.textContent = 'query';
    action.textContent = 'action';

    header.className = 'djangoql-favorite__table-header';
    header.appendChild(getRowUI(name, query, action));

    return header;
  }

  function getTableBody(data) {
    tableBody = document.createElement('div');

    tableBody.className = 'djangoql-favorite__table-body';

    data.favorite_query_list.forEach(function (item) {
      tableBody.appendChild(getFavoriteQueryRow(item));
    });

    if (data.favorite_query_list.length === 0) {
      tableBody.appendChild(getEmptyRow());
    }

    return tableBody;
  }

  function insertControlPanelUI() {
    starButton = document.createElement('div');
    starButton.className = 'djangoql-favorite__star-button';
    starButton.textContent = starIcon;
    starButton.setAttribute('title', 'Add query to favorite');
    starButton.addEventListener('click', starButtonListenerOnClick);
    insertAfter(starButton, searchBar);

    listButton = document.createElement('div');
    listButton.className = 'djangoql-favorite__list-button';
    listButton.textContent = listIcon;
    listButton.setAttribute('title', 'Show favorite query list');
    listButton.addEventListener('click', listButtonListenerOnClick);
    document.addEventListener('click', documentListenerForListButtonOnClick);
    insertAfter(listButton, starButton);
  }

  function insertTableUI() {
    getFavoriteQueries().then(function (data) {
      table = document.createElement('div');
      table.className = 'djangoql-favorite__table';
      document.body.appendChild(table);

      table.appendChild(getTableHeader());
      table.appendChild(getTableBody(data));
    });
  }

  function insertFavoriteQueryUI() {
    window.onload = function () {
      searchBar = document.getElementById('searchbar');
      searchForm = document.getElementById('changelist-search');

      insertControlPanelUI();
      insertTableUI();
    };
  }

  insertFavoriteQueryUI();
}());
