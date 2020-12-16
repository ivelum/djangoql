(function (root, factory) {
  'use strict';

  /* global define, require */
  if (!String.prototype.trim) {
    // eslint-disable-next-line no-extend-native
    String.prototype.trim = function () {
      return this.replace(/^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g, '');
    };
  }
  /* eslint-disable */
  if (!String.prototype.startsWith) {
    // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/startsWith#Polyfill
    Object.defineProperty(String.prototype, 'startsWith', {
      value: function (search, rawPos) {
        var pos = rawPos > 0 ? rawPos | 0 : 0;
        return this.substring(pos, pos + search.length) === search;
      }
    });
  }
  if (!String.prototype.endsWith) {
    // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/endsWith#Polyfill
    String.prototype.endsWith = function(search, this_len) {
      if (this_len === undefined || this_len > this.length) {
        this_len = this.length;
      }
      return this.substring(this_len - search.length, this_len) === search;
    };
  }
  /* eslint-enable */

  if (typeof define === 'function' && define.amd) {
    // AMD. Register as an anonymous module.
    define('DjangoQL', ['Lexer', 'LRUCache'], factory);
  } else if (typeof exports === 'object') {
    // Node. Does not work with strict CommonJS, but
    // only CommonJS-like environments that support module.exports,
    // like Node.
    module.exports = factory(require('Lexer'), require('LRUCache'));  // eslint-disable-line
  } else {
    // Browser globals (root is window)
    root.DjangoQL = factory(root.Lexer, root.LRUCache);  // eslint-disable-line
  }
}(this, function (Lexer, LRUCache) {
  'use strict';

  var reIntValue = '(-?0|-?[1-9][0-9]*)';
  var reFractionPart = '\\.[0-9]+';
  var reExponentPart = '[eE][+-]?[0-9]+';
  var intRegex = new RegExp(reIntValue);
  var floatRegex = new RegExp(
      reIntValue + reFractionPart + reExponentPart + '|' +
      reIntValue + reFractionPart + '|' +
      reIntValue + reExponentPart);
  var reLineTerminators = '\\n\\r\\u2028\\u2029';
  var reEscapedChar = '\\\\[\\\\"/bfnrt]';
  var reEscapedUnicode = '\\\\u[0-9A-Fa-f]{4}';
  var reStringChar = '[^\\"\\\\' + reLineTerminators + ']';
  var stringRegex = new RegExp(
      '\\"(' + reEscapedChar +
      '|' + reEscapedUnicode +
      '|' + reStringChar + ')*\\"');
  var nameRegex = /[_A-Za-z][_0-9A-Za-z]*(\.[_A-Za-z][_0-9A-Za-z]*)*/;
  var reNotFollowedByName = '(?![_0-9A-Za-z])';
  var whitespaceRegex = /[ \t\v\f\u00A0]+/;

  var lexer = new Lexer(function () {
    // Silently swallow any lexer errors
  });

  function token(name, value) {
    return { name: name, value: value };
  }

  lexer.addRule(whitespaceRegex, function () { /* ignore whitespace */ });
  lexer.addRule(/\./, function (l) { return token('DOT', l); });
  lexer.addRule(/,/, function (l) { return token('COMMA', l); });
  lexer.addRule(new RegExp('or' + reNotFollowedByName), function (l) {
    return token('OR', l);
  });
  lexer.addRule(new RegExp('and' + reNotFollowedByName), function (l) {
    return token('AND', l);
  });
  lexer.addRule(new RegExp('not' + reNotFollowedByName), function (l) {
    return token('NOT', l);
  });
  lexer.addRule(new RegExp('in' + reNotFollowedByName), function (l) {
    return token('IN', l);
  });
  lexer.addRule(new RegExp('True' + reNotFollowedByName), function (l) {
    return token('TRUE', l);
  });
  lexer.addRule(new RegExp('False' + reNotFollowedByName), function (l) {
    return token('FALSE', l);
  });
  lexer.addRule(new RegExp('None' + reNotFollowedByName), function (l) {
    return token('NONE', l);
  });
  lexer.addRule(nameRegex, function (l) { return token('NAME', l); });
  lexer.addRule(stringRegex, function (l) {
    // Trim leading and trailing quotes
    return token('STRING_VALUE', l.slice(1, l.length - 1));
  });
  lexer.addRule(intRegex, function (l) { return token('INT_VALUE', l); });
  lexer.addRule(floatRegex, function (l) { return token('FLOAT_VALUE', l); });
  lexer.addRule(/\(/, function (l) { return token('PAREN_L', l); });
  lexer.addRule(/\)/, function (l) { return token('PAREN_R', l); });
  lexer.addRule(/=/, function (l) { return token('EQUALS', l); });
  lexer.addRule(/!=/, function (l) { return token('NOT_EQUALS', l); });
  lexer.addRule(/>/, function (l) { return token('GREATER', l); });
  lexer.addRule(/>=/, function (l) { return token('GREATER_EQUAL', l); });
  lexer.addRule(/</, function (l) { return token('LESS', l); });
  lexer.addRule(/<=/, function (l) { return token('LESS_EQUAL', l); });
  lexer.addRule(/~/, function (l) { return token('CONTAINS', l); });
  lexer.addRule(/!~/, function (l) { return token('NOT_CONTAINS', l); });
  lexer.lexAll = function () {
    var match;
    var result = [];
    while (match = this.lex()) {  // eslint-disable-line no-cond-assign
      match.start = this.index - match.value.length;
      match.end = this.index;
      result.push(match);
    }
    return result;
  };

  function suggestion(text, snippetBefore, snippetAfter) {
    // text is being displayed in completion box and pasted when you hit Enter.
    // snippetBefore is an optional extra text to be pasted before main text.
    // snippetAfter is an optional text to be pasted after. It may also include
    // "|" symbol to designate desired cursor position after paste.
    return {
      text: text,
      snippetBefore: snippetBefore || '',
      snippetAfter: snippetAfter || ''
    };
  }

  // Main DjangoQL object
  var DjangoQL = function (options) {
    var cacheSize = 100;

    this.options = options;
    this.currentModel = null;
    this.models = {};
    this.suggestionsAPIUrl = null;

    this.token = token;
    this.lexer = lexer;

    this.prefix = '';
    this.suggestions = [];
    this.selected = null;
    this.valuesCaseSensitive = false;
    this.highlightCaseSensitive = true;

    this.textarea = null;
    this.completion = null;
    this.completionUL = null;
    this.completionEnabled = false;

    // Initialization
    if (!this.isObject(options)) {
      this.logError('Please pass an object with initialization parameters');
      return;
    }
    this.loadIntrospections(options.introspections);
    if (typeof options.selector === 'string') {
      this.textarea = document.querySelector(options.selector);
    } else {
      this.textarea = options.selector;
    }
    if (!this.textarea) {
      this.logError('Element not found by selector: ' + options.selector);
      return;
    }
    if (this.textarea.tagName !== 'TEXTAREA') {
      this.logError('selector must be pointing to <textarea> element, but ' +
          this.textarea.tagName + ' was found');
      return;
    }
    if (options.valuesCaseSensitive) {
      this.valuesCaseSensitive = true;
    }
    if (options.cacheSize) {
      if (parseInt(options.cacheSize, 10) !== options.cacheSize
          || options.cacheSize < 1) {
        this.logError('cacheSize must be a positive integer');
      } else {
        cacheSize = options.cacheSize;
      }
    }
    this.suggestionsCache = new LRUCache(cacheSize);
    this.debouncedLoadFieldOptions = this.debounce(
      this.loadFieldOptions.bind(this),
      300);
    this.loading = false;

    this.enableCompletion = this.enableCompletion.bind(this);
    this.disableCompletion = this.disableCompletion.bind(this);

    // these handlers are re-used more than once in the code below,
    // so it's handy to have them already bound
    this.onCompletionMouseClick = this.onCompletionMouseClick.bind(this);
    this.onCompletionMouseDown = this.onCompletionMouseDown.bind(this);
    this.popupCompletion = this.popupCompletion.bind(this);
    this.debouncedRenderCompletion = this.debounce(
        this.renderCompletion.bind(this),
        50);

    // Bind event handlers and initialize completion & textSize containers
    this.textarea.setAttribute('autocomplete', 'off');
    this.textarea.addEventListener('keydown', this.onKeydown.bind(this));
    this.textarea.addEventListener('blur', this.hideCompletion.bind(this));
    this.textarea.addEventListener('click', this.popupCompletion);
    if (options.autoResize) {
      this.textareaResize = this.textareaResize.bind(this);
      this.textarea.style.resize = 'none';
      this.textarea.style.overflow = 'hidden';
      this.textarea.addEventListener('input', this.textareaResize);
      this.textareaResize();
      // There could be a situation when fonts are not loaded yet at this
      // point. When fonts are finally loaded it could make textarea looking
      // weird - for example in Django 1.9+ last line won't fit. To fix this
      // we call .textareaResize() once again when window is fully loaded.
      window.addEventListener('load', this.textareaResize);
    } else {
      this.textareaResize = null;
      // Catch resize events and re-position completion box.
      // See http://stackoverflow.com/a/7055239
      this.textarea.addEventListener(
          'mouseup', this.renderCompletion.bind(this, true));
      this.textarea.addEventListener(
          'mouseout', this.renderCompletion.bind(this, true));
    }

    this.createCompletionElement();
  };

  // Backward compatibility
  DjangoQL.init = function (options) {
    return new DjangoQL(options);
  };

  DjangoQL.DOMReady = function (callback) {
    if (document.readyState !== 'loading') {
      callback();
    } else {
      document.addEventListener('DOMContentLoaded', callback);
    }
  };

  DjangoQL.prototype = {
    createCompletionElement: function () {
      var options = this.options;
      var syntaxHelp;

      if (!this.completion) {
        this.completion = document.createElement('div');
        this.completion.className = 'djangoql-completion';
        document.querySelector('body').appendChild(this.completion);
        this.completionUL = document.createElement('ul');
        this.completionUL.onscroll = this.throttle(
          this.onCompletionScroll.bind(this),
          50);
        this.completion.appendChild(this.completionUL);
        if (typeof options.syntaxHelp === 'string') {
          syntaxHelp = document.createElement('p');
          syntaxHelp.className = 'syntax-help';
          syntaxHelp.innerHTML = '<a href="' + options.syntaxHelp +
              '" target="_blank">Syntax Help</a>';
          syntaxHelp.addEventListener('mousedown', function (e) {
            // This is needed to prevent conflict with textarea.onblur event
            // handler, which tries to hide the completion box and therefore
            // makes Syntax Help link malfunctional.
            e.preventDefault();
          });
          this.completion.appendChild(syntaxHelp);
        }

        this.completionEnabled = options.hasOwnProperty('completionEnabled') ?
          options.completionEnabled :
          true;
      }
    },

    destroyCompletionElement: function () {
      if (this.completion) {
        this.completion.parentNode.removeChild(this.completion);
        this.completion = null;
        this.completionEnabled = false;
      }
    },

    enableCompletion: function () {
      this.completionEnabled = true;
    },

    disableCompletion: function () {
      this.completionEnabled = false;
      this.hideCompletion();
    },

    getJson: function (url, settings) {
      this.loading = true;

      var onLoadError = function () {
        this.loading = false;
        this.request = null;
        this.logError('failed to fetch from ' + url);
      }.bind(this);

      if (this.request) {
        this.request.abort();
      }
      this.request = new XMLHttpRequest();

      this.request.open('GET', url, true);
      this.request.onload = function () {
        this.loading = false;
        if (this.request.status === 200) {
          if (typeof settings.success === 'function') {
            settings.success(JSON.parse(this.request.responseText));
          }
        } else {
          onLoadError();
        }
        this.request = null;
      }.bind(this);
      this.request.ontimeout = onLoadError;
      this.request.onerror = onLoadError;
      /* eslint-disable max-len */
      // Workaround for IE9, see
      // https://cypressnorth.com/programming/internet-explorer-aborting-ajax-requests-fixed/
      /* eslint-enable max-len */
      this.request.onprogress = function () {};
      window.setTimeout(this.request.send.bind(this.request));
    },

    loadIntrospections: function (introspections) {
      var initIntrospections = function (data) {
        this.currentModel = data.current_model;
        this.models = data.models;
        this.suggestionsAPIUrl = data.suggestions_api_url;
      }.bind(this);

      if (typeof introspections === 'string') {
        // treat as URL
        this.getJson(introspections, { success: initIntrospections });
      } else if (this.isObject(introspections)) {
        initIntrospections(introspections);
      } else {
        this.logError(
            'introspections parameter is expected to be either URL or ' +
            'object with definitions, but ' + introspections + ' was found');
      }
    },

    isObject: function (obj) {
      return (({}).toString.call(obj) === '[object Object]');
    },

    debounce: function (func, wait, immediate) {
      // Borrowed from Underscore.js
      var args;
      var context;
      var result;
      var timeout;
      var timestamp;

      var later = function () {
        var last = Date.now() - timestamp;
        if (last < wait && last >= 0) {
          timeout = setTimeout(later, wait - last);
        } else {
          timeout = null;
          if (!immediate) {
            result = func.apply(context, args);
            if (!timeout) {
              args = null;
              context = null;
            }
          }
        }
      };

      return function () {
        var callNow;
        context = this;
        args = arguments;
        timestamp = Date.now();
        callNow = immediate && !timeout;
        if (!timeout) timeout = setTimeout(later, wait);
        if (callNow) {
          result = func.apply(context, args);
          args = null;
          context = null;
        }
        return result;
      };
    },

    throttle: function (func, wait, options) {
      // Borrowed from Underscore.js
      var timeout;
      var context;
      var args;
      var result;
      var previous = 0;
      var later;
      var throttled;

      if (!options) {
        options = {};
      }

      later = function () {
        previous = options.leading === false ? 0 : new Date().getTime();
        timeout = null;
        result = func.apply(context, args);
        if (!timeout) {
          context = null;
          args = null;
        }
      };

      throttled = function () {
        var now = new Date().getTime();
        var remaining;

        if (!previous && options.leading === false) {
          previous = now;
        }
        remaining = wait - (now - previous);
        context = this;
        args = arguments;
        if (remaining <= 0 || remaining > wait) {
          if (timeout) {
            window.clearTimeout(timeout);
            timeout = null;
          }
          previous = now;
          result = func.apply(context, args);
          if (!timeout) {
            context = null;
            args = null;
          }
        } else if (!timeout && options.trailing !== false) {
          timeout = window.setTimeout(later, remaining);
        }
        return result;
      };

      throttled.cancel = function () {
        window.clearTimeout(timeout);
        previous = 0;
        timeout = null;
        context = null;
        args = null;
      };

      return throttled;
    },

    setUrlParams: function (url, params) {
      var parts = url.split('?');
      var path = parts[0];
      var queryString = parts.slice(1).join('?');
      var pairs = queryString.split('&');
      var pair;
      var key;
      var value;
      var i;

      for (key in params) {
        if (params.hasOwnProperty(key)) {
          key = encodeURI(key);
          value = encodeURI(params[key]);
          i = pairs.length;
          while (i--) {
            pair = pairs[i].split('=');
            if (pair[0] === key) {
              pair[1] = value;
              pairs[i] = pair.join('=');
              break;
            }
          }
          if (i < 0) {
            pairs.push(key + '=' + value);
          }
        }
      }
      queryString = pairs.join('&');
      return queryString ? [path, queryString].join('?') : path;
    },

    logError: function (message) {
      console.error('DjangoQL: ' + message);  // eslint-disable-line no-console
    },

    onCompletionMouseClick: function (e) {
      this.selectCompletion(
        parseInt(e.currentTarget.getAttribute('data-index'), 10)
      );
    },

    onCompletionMouseDown: function (e) {
      // This is needed to prevent 'blur' event on textarea
      e.preventDefault();
    },

    onKeydown: function (e) {
      switch (e.keyCode) {
        case 38:  // up arrow
          if (this.suggestions.length) {
            if (this.selected === null) {
              this.selected = this.suggestions.length - 1;
            } else if (this.selected === 0) {
              this.selected = null;
            } else {
              this.selected -= 1;
            }
            this.renderCompletion();
            e.preventDefault();
          }
          break;

        case 40:  // down arrow
          if (this.suggestions.length) {
            if (this.selected === null) {
              this.selected = 0;
            } else if (this.selected < this.suggestions.length - 1) {
              this.selected += 1;
            } else {
              this.selected = null;
            }
            this.renderCompletion();
            e.preventDefault();
          }
          break;

        case 9:   // Tab
          if (this.selected !== null) {
            this.selectCompletion(this.selected);
            e.preventDefault();
          }
          break;

        case 13:  // Enter
          if (this.selected !== null) {
            this.selectCompletion(this.selected);
          } else {
            // Technically this is a textarea, due to automatic multi-line
            // feature, but other than that it should look and behave like
            // a normal input. So expected behavior when pressing Enter is
            // to submit the form, not to add a new line.
            if (typeof this.options.onSubmit === 'function') {
              this.options.onSubmit(this.textarea.value);
            } else {
              e.currentTarget.form.submit();
            }
          }
          e.preventDefault();
          break;

        case 27:  // Esc
          this.hideCompletion();
          break;

        case 16:  // Shift
        case 17:  // Ctrl
        case 18:  // Alt
        case 91:  // Windows Key or Left Cmd on Mac
        case 93:  // Windows Menu or Right Cmd on Mac
          // Control keys shouldn't trigger completion popup
          break;

        default:
          // When keydown is fired input value has not been updated yet,
          // so we need to wait
          window.setTimeout(this.popupCompletion, 10);
          break;
      }
    },

    textareaResize: function () {
      // Automatically grow/shrink textarea to have the contents always visible
      var style = window.getComputedStyle(this.textarea, null);
      var heightOffset = parseFloat(style.paddingTop) +
          parseFloat(style.paddingBottom);
      this.textarea.style.height = '5px';
      // dirty hack, works for Django admin styles only.
      // Ping me if you know how to get rid of "+1"
      this.textarea.style.height = (this.textarea.scrollHeight - heightOffset) +
          1 + 'px';
    },

    popupCompletion: function () {
      this.generateSuggestions();
      this.renderCompletion();
    },

    selectCompletion: function (index) {
      var context = this.getContext(
        this.textarea.value,
        this.textarea.selectionStart
      );
      var currentFullToken = context.currentFullToken;
      var textValue = this.textarea.value;
      var startPos = this.textarea.selectionStart - context.prefix.length;
      var tokenEndPos = null;

      // cutting current token from the string
      if (currentFullToken) {
        tokenEndPos = currentFullToken.end;
        textValue = (
          textValue.slice(0, startPos) + textValue.slice(tokenEndPos)
        );
      }

      var textBefore = textValue.slice(0, startPos);
      var textAfter = textValue.slice(startPos);
      // preventing double spaces after pasting the suggestion
      textAfter = textAfter.trim();

      var completion = this.suggestions[index];
      var snippetBefore = completion.snippetBefore;
      var snippetAfter = completion.snippetAfter;
      var snippetAfterParts = snippetAfter.split('|');
      if (snippetAfterParts.length > 1) {
        snippetAfter = snippetAfterParts.join('');
        if (!snippetBefore && !completion.text) {
          snippetBefore = snippetAfterParts[0];
          snippetAfter = snippetAfterParts[1];
        }
      }
      if (textBefore.endsWith(snippetBefore)) {
        snippetBefore = '';
      }
      if (textAfter.startsWith(snippetAfter)) {
        snippetAfter = '';
      }
      var textToPaste = snippetBefore + completion.text + snippetAfter;
      var cursorPosAfter = textBefore.length + textToPaste.length;
      if (snippetAfterParts.length > 1) {
        cursorPosAfter -= snippetAfterParts[1].length;
      }

      this.textarea.value = textBefore + textToPaste + textAfter;
      this.textarea.focus();
      this.textarea.setSelectionRange(cursorPosAfter, cursorPosAfter);
      this.selected = null;
      if (this.textareaResize) {
        this.textareaResize();
      }
      this.generateSuggestions(this.textarea);
      this.renderCompletion();
    },

    hideCompletion: function () {
      this.selected = null;
      if (this.completion) {
        this.completion.style.display = 'none';
      }
    },

    escapeRegExp: function (str) {
      // http://stackoverflow.com
      // /questions/3446170/escape-string-for-use-in-javascript-regex
      return str.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, '\\$&');  // eslint-disable-line
    },

    highlight: function (text, highlight) {
      if (!highlight || !text) {
        return text;
      } else if (this.highlightCaseSensitive) {
        return text.split(highlight).join('<b>' + highlight + '</b>');
      }
      return text.replace(
          new RegExp('(' + this.escapeRegExp(highlight) + ')', 'ig'),
          '<b>$1</b>');
    },

    renderCompletion: function (dontForceDisplay) {
      var currentLi;
      var i;
      var completionRect;
      var currentLiRect;
      var inputRect;
      var li;
      var liLen;
      var suggestionsLen;
      var loadingElement;

      if (!this.completionEnabled) {
        this.hideCompletion();
        return;
      }

      if (dontForceDisplay && this.completion.style.display === 'none') {
        return;
      }
      if (!this.suggestions.length && !this.loading) {
        this.hideCompletion();
        return;
      }

      suggestionsLen = this.suggestions.length;
      li = [].slice.call(this.completionUL.querySelectorAll('li[data-index]'));
      liLen = li.length;

      // Update or create necessary elements
      for (i = 0; i < suggestionsLen; i++) {
        if (i < liLen) {
          currentLi = li[i];
        } else {
          currentLi = document.createElement('li');
          currentLi.setAttribute('data-index', i);
          currentLi.addEventListener('click', this.onCompletionMouseClick);
          currentLi.addEventListener('mousedown', this.onCompletionMouseDown);
          this.completionUL.appendChild(currentLi);
        }
        currentLi.innerHTML = this.highlight(
            this.suggestions[i].text,
            this.prefix);
        if (i === this.selected) {
          currentLi.className = 'active';
          currentLiRect = currentLi.getBoundingClientRect();
          completionRect = this.completionUL.getBoundingClientRect();
          if (currentLiRect.bottom > completionRect.bottom) {
            this.completionUL.scrollTop = this.completionUL.scrollTop + 2 +
                (currentLiRect.bottom - completionRect.bottom);
          } else if (currentLiRect.top < completionRect.top) {
            this.completionUL.scrollTop = this.completionUL.scrollTop - 2 -
                (completionRect.top - currentLiRect.top);
          }
        } else {
          currentLi.className = '';
        }
      }
      // Remove redundant elements
      while (liLen > suggestionsLen) {
        liLen--;
        li[liLen].removeEventListener('click', this.onCompletionMouseClick);
        li[liLen].removeEventListener('mousedown', this.onCompletionMouseDown);
        this.completionUL.removeChild(li[liLen]);
      }

      loadingElement = this.completionUL.querySelector('li.djangoql-loading');

      if (this.loading) {
        if (!loadingElement) {
          loadingElement = document.createElement('li');
          loadingElement.className = 'djangoql-loading';
          loadingElement.innerHTML = '&nbsp;';
          this.completionUL.appendChild(loadingElement);
        }
      } else if (loadingElement) {
        this.completionUL.removeChild(loadingElement);
      }

      inputRect = this.textarea.getBoundingClientRect();
      this.completion.style.top = window.pageYOffset + inputRect.top +
          inputRect.height + 'px';
      this.completion.style.left = inputRect.left + 'px';
      this.completion.style.display = 'block';
    },

    resolveName: function (name) {
      // Walk through introspection definitions and get target model and field
      var f;
      var i;
      var l;
      var nameParts = name.split('.');
      var model = this.currentModel;
      var field = null;

      if (model) {
        for (i = 0, l = nameParts.length; i < l; i++) {
          f = this.models[model][nameParts[i]];
          if (!f) {
            model = null;
            field = null;
            break;
          } else if (f.type === 'relation') {
            model = f.relation;
            field = null;
          } else {
            field = nameParts[i];
          }
        }
      }
      return { model: model, field: field };
    },

    getContext: function (text, cursorPos) {
      // This function returns an object with the following 4 properties:
      var prefix;        // text already entered by user in the current scope
      var scope = null;  // 'field', 'comparison', 'value', 'logical' or null
      var model = null;  // model, set for 'field', 'comparison' and 'value'
      var field = null;  // field, set for 'comparison' and 'value'

      var whitespace;
      var nameParts;
      var resolvedName;
      var lastToken = null;
      var nextToLastToken = null;
      var tokens = this.lexer.setInput(text.slice(0, cursorPos)).lexAll();
      var allTokens = this.lexer.setInput(text).lexAll();
      var currentFullToken = null;
      if (tokens.length && tokens[tokens.length - 1].end >= cursorPos) {
        // if cursor is positioned on the last token then remove it.
        // We are only interested in tokens preceding current.
        currentFullToken = allTokens[tokens.length - 1];
        tokens.pop();
      }
      if (tokens.length) {
        lastToken = tokens[tokens.length - 1];
        if (tokens.length > 1) {
          nextToLastToken = tokens[tokens.length - 2];
        }
      }

      // Current token which is currently being typed may be not complete yet,
      // so lexer may fail to recognize it correctly. So we define current token
      // prefix as a string without whitespace positioned after previous token
      // and until current cursor position.
      prefix = text.slice(lastToken ? lastToken.end : 0, cursorPos);
      whitespace = prefix.match(whitespaceRegex);
      if (whitespace) {
        prefix = prefix.slice(whitespace[0].length);
      }
      if (prefix === '(') {
        // Paren should not be a part of suggestion
        prefix = '';
      }

      if (prefix === ')' && !whitespace) {
        // Nothing to suggest right after right paren
      } else if (!lastToken ||
          (['AND', 'OR'].indexOf(lastToken.name) >= 0 && whitespace) ||
          (prefix === '.' && lastToken && !whitespace) ||
          (lastToken.name === 'PAREN_L' && (!nextToLastToken ||
              ['AND', 'OR'].indexOf(nextToLastToken.name) >= 0))) {
        scope = 'field';
        model = this.currentModel;
        if (prefix === '.') {
          prefix = text.slice(lastToken.start, cursorPos);
        }
        nameParts = prefix.split('.');
        if (nameParts.length > 1) {
          // use last part as a prefix, analyze preceding parts to get the model
          prefix = nameParts.pop();
          resolvedName = this.resolveName(nameParts.join('.'));
          if (resolvedName.model && !resolvedName.field) {
            model = resolvedName.model;
          } else {
            // if resolvedName.model is null that means that model wasn't found.
            // if resolvedName.field is NOT null that means that the name
            // preceding current prefix is a concrete field and not a relation,
            // and therefore it can't have any properties.
            scope = null;
            model = null;
          }
        }
      } else if (lastToken && whitespace &&
          nextToLastToken && nextToLastToken.name === 'NAME' &&
          ['EQUALS', 'NOT_EQUALS', 'CONTAINS', 'NOT_CONTAINS', 'GREATER_EQUAL',
            'GREATER', 'LESS_EQUAL', 'LESS'].indexOf(lastToken.name) >= 0) {
        resolvedName = this.resolveName(nextToLastToken.value);
        if (resolvedName.model) {
          scope = 'value';
          model = resolvedName.model;
          field = resolvedName.field;
          if (prefix[0] === '"' && (this.models[model][field].type === 'str'
              || this.models[model][field].options)) {
            prefix = prefix.slice(1);
          }
        }
      } else if (lastToken && whitespace && lastToken.name === 'NAME') {
        resolvedName = this.resolveName(lastToken.value);
        if (resolvedName.model) {
          scope = 'comparison';
          model = resolvedName.model;
          field = resolvedName.field;
        }
      } else if (lastToken && whitespace &&
          ['PAREN_R', 'INT_VALUE', 'FLOAT_VALUE', 'STRING_VALUE']
              .indexOf(lastToken.name) >= 0) {
        scope = 'logical';
      }
      return {
        prefix: prefix,
        scope: scope,
        model: model,
        field: field,
        currentFullToken: currentFullToken
      };
    },

    getCurrentFieldOptions: function () {
      var input = this.textarea;
      var context = this.getContext(input.value, input.selectionStart);
      var model = this.models[context.model];
      var field = context.field && model[context.field];
      var fieldOptions = {
        cacheKey: null,
        context: context,
        field: field,
        model: model,
        options: null
      };

      if (context.scope !== 'value' || !field || !field.options) {
        return null;
      }
      if (Array.isArray(field.options)) {
        fieldOptions.options = field.options;
      } else if (field.options === true) {
        // Means get via API
        if (!this.suggestionsAPIUrl) {
          return null;
        }
        fieldOptions.cacheKey = context.model + '.' + context.field
          + '|' + context.prefix;
      }
      return fieldOptions;
    },

    loadFieldOptions: function (loadMore) {
      var fieldOptions = this.getCurrentFieldOptions() || {};
      var context = fieldOptions.context;
      var cached;
      var requestUrl;
      var requestParams;

      if (!fieldOptions.cacheKey) {
        // The context has likely changed, user's cursor is in another position
        return;
      }
      requestParams = {
        field: context.model + '.' + context.field,
        search: context.prefix
      };

      cached = this.suggestionsCache.get(fieldOptions.cacheKey) || {};
      if (loadMore && cached.has_next) {
        requestParams.page = cached.page ? cached.page + 1 : 1;
      } else if (cached.page) {
        // At least the first page is already loaded
        return;
      }

      cached.loading = true;
      this.suggestionsCache.set(fieldOptions.cacheKey, cached);

      requestUrl = this.setUrlParams(this.suggestionsAPIUrl, requestParams);
      this.getJson(requestUrl, {
        success: function (data) {
          var cached = this.suggestionsCache.get(fieldOptions.cacheKey) || {};
          if (data.page - 1 !== (cached.page || 0)) {
            // either pages were loaded out of order,
            // or cache is no longer exists
            return;
          }
          data.items = (cached.items || []).concat(data.items);
          this.suggestionsCache.set(fieldOptions.cacheKey, data);
          this.loading = false;
          this.populateFieldOptions();
          this.renderCompletion();
        }.bind(this)
      });
      // Render 'loading' element
      this.populateFieldOptions();
      this.renderCompletion();
    },

    populateFieldOptions: function (loadMore) {
      var fieldOptions = this.getCurrentFieldOptions();
      if (fieldOptions === null) {
        // 1) we are out of field options context
        // 2) field has no options
        return;
      }
      var options = fieldOptions.options;
      var prefix = fieldOptions.context && fieldOptions.context.prefix;
      var cached;

      if (options) {
        // filter them locally
        if (this.valuesCaseSensitive) {
          options = options.filter(function (item) {
            // Case-sensitive
            return item.indexOf(prefix) >= 0;
          });
        } else {
          options = options.filter(function (item) {
            // Case-insensitive
            return item.toLowerCase().indexOf(prefix.toLowerCase()) >= 0;
          });
        }
      } else {
        this.suggestions = [];
        if (!fieldOptions.cacheKey) {
          return;
        }
        cached = this.suggestionsCache.get(fieldOptions.cacheKey) || {};
        options = cached.items || [];
        if (!cached.loading
            && (!cached.page || (loadMore && cached.has_next))) {
          this.debouncedLoadFieldOptions(loadMore);
        }
        if (!options.length) {
          // Should we show 'no results' message?
          return;
        }
      }

      this.highlightCaseSensitive = this.valuesCaseSensitive;
      this.suggestions = options.map(function (f) {
        return suggestion(f, '"', '"');
      });
    },

    onCompletionScroll: function () {
      var rectHeight = this.completionUL.getBoundingClientRect().height;
      var scrollBottom = this.completionUL.scrollTop + rectHeight;
      if (scrollBottom > rectHeight
          && scrollBottom > (this.completionUL.scrollHeight - rectHeight)) {
        // TODO: add some checks of context?
        this.populateFieldOptions(true);
      }
    },

    generateSuggestions: function () {
      var input = this.textarea;
      var context;
      var model;
      var field;
      var suggestions;
      var snippetAfter;
      var searchFilter;

      if (!this.completionEnabled) {
        this.prefix = '';
        this.suggestions = [];
        return;
      }

      if (!this.currentModel) {
        // Introspections are not loaded yet
        return;
      }
      if (input.selectionStart !== input.selectionEnd) {
        // We shouldn't show suggestions when something is selected
        this.prefix = '';
        this.suggestions = [];
        return;
      }

      // default search filter - find anywhere in the string, case-sensitive
      searchFilter = function (item) {
        return item.text.indexOf(this.prefix) >= 0;
      }.bind(this);
      // default highlight mode - case sensitive
      this.highlightCaseSensitive = true;

      context = this.getContext(input.value, input.selectionStart);
      this.prefix = context.prefix;
      model = this.models[context.model];
      field = context.field && model[context.field];

      switch (context.scope) {
        case 'field':
          this.suggestions = Object.keys(model).map(function (f) {
            return suggestion(f, '', model[f].type === 'relation' ? '.' : ' ');
          });
          break;

        case 'comparison':
          suggestions = ['=', '!='];
          snippetAfter = ' ';
          if (field && field.type !== 'bool') {
            if (field.type === 'str') {
              suggestions.push('~');
              suggestions.push('!~');
              snippetAfter = ' "|"';
            } else if (field.type === 'date' || field.type === 'datetime'
                       || field.options) {
              snippetAfter = ' "|"';
            }
            Array.prototype.push.apply(suggestions, ['>', '>=', '<', '<=']);
          }
          this.suggestions = suggestions.map(function (s) {
            return suggestion(s, '', snippetAfter);
          });
          if (field && field.type !== 'bool') {
            if (['str', 'date', 'datetime'].indexOf(field.type) >= 0
                || field.options) {
              snippetAfter = ' ("|")';
            } else {
              snippetAfter = ' (|)';
            }
            this.suggestions.push(suggestion('in', '', snippetAfter));
            this.suggestions.push(suggestion('not in', '', snippetAfter));
          }
          // use "starts with" search filter instead of default
          searchFilter = function (item) {
            // See http://stackoverflow.com/a/4579228
            return item.text.lastIndexOf(this.prefix, 0) === 0;
          }.bind(this);
          break;

        case 'value':
          if (!field) {
            // related field
            this.suggestions = [suggestion('None', '', ' ')];
          } else if (field.options) {
            this.prefix = context.prefix;
            this.populateFieldOptions();
          } else if (field.type === 'bool') {
            this.suggestions = [
              suggestion('True', '', ' '),
              suggestion('False', '', ' ')
            ];
            if (field.nullable) {
              this.suggestions.push(suggestion('None', '', ' '));
            }
          } else if (field.type === 'unknown') {
            // unknown field type, reset suggestions
            this.prefix = '';
            this.suggestions = [];
          }
          break;

        case 'logical':
          this.suggestions = [
            suggestion('and', '', ' '),
            suggestion('or', '', ' ')
          ];
          break;

        default:
          this.prefix = '';
          this.suggestions = [];
      }
      this.suggestions = this.suggestions.filter(searchFilter);
      if (this.suggestions.length === 1) {
        this.selected = 0;  // auto-select the only suggested item
      } else {
        this.selected = null;
      }
    }

  };

  return DjangoQL;

}));
