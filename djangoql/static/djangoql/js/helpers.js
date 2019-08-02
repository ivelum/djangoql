(function (root, factory) {
  'use strict';

  /* global define, require */

  if (typeof define === 'function' && define.amd) {
    // AMD. Register as an anonymous module.
    define('DjangoQLHelpers', [], factory);
  } else if (typeof exports === 'object') {
    // Node. Does not work with strict CommonJS, but
    // only CommonJS-like environments that support module.exports,
    // like Node.
    module.exports = factory();  // eslint-disable-line
  } else {
    // Browser globals (root is window)
    root.DjangoQLHelpers = factory();  // eslint-disable-line
  }
}(this, function () {
  'use strict';

  return {
    parseQueryString: function () {
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
    },

    updateURLParameter: function (url, param, paramVal) {
      var newAdditionalURL = '';
      var tempArray = url.split('?');
      var baseURL = tempArray[0];
      var additionalURL = tempArray[1];
      var temp = '';
      var i;
      var rowsTxt = '';
      if (additionalURL) {
        tempArray = additionalURL.split('&');
        for (i = 0; i < tempArray.length; i++) {
          if (tempArray[i].split('=')[0] !== param) {
            newAdditionalURL += temp + tempArray[i];
            temp = '&';
          }
        }
      }

      if (paramVal !== null) {
        rowsTxt = temp + '' + param + '=' + paramVal;
      }
      return baseURL + '?' + newAdditionalURL + rowsTxt;
    },

    getCookie: function (name) {
      var cookieValue = null;
      var i;
      var cookie;
      var cookies = document.cookie.split(';');
      if (document.cookie && document.cookie !== '') {
        for (i = 0; i < cookies.length; i++) {
          cookie = cookies[i].trim();
          // Does this cookie string begin with the name we want?
          if (cookie.substring(0, name.length + 1) === (name + '=')) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
          }
        }
      }
      return cookieValue;
    }
  };
}));
