'use strict';

/* global SavedQueries, DjangoQL, expect, describe, before, beforeEach, it,
   afterEach */

/**
 * Simple storage implementation with the interface similiar
 * to original QueryRepo
 */
var QueryRepo = {
  get: function (id, callback) {
    var result = this.objects[id];
    if (callback) {
      callback(result);
      return null;
    }
    return result;
  },
  save: function (obj, callback) {
    // clone object to avoid side effects
    var query = Object.assign({}, obj);
    if (!query.id) {
      // query doesn't exists, generate id and insert object
      query.id = this.generateId();
    }
    this.objects[query.id] = query;
    if (callback) {
      callback(query.id);
      return null;
    }
    return query.id;
  },
  remove: function (id, callback) {
    delete this.objects[id];
    if (callback) {
      callback();
    }
  },
  list: function (callback) {
    var result = Object.values(this.objects);
    if (callback) {
      callback(result);
    }
    return result;
  },
  generateId: function () {
    var keys = Object.keys(this.objects);
    if (keys.length) {
      return Math.max.apply(Math, keys) + 1;
    }
    return 1;
  },
  objects: {}
};

/**
 * Generates random string
 */
function randomString() {
  return Math.random().toString(36).substring(7);
}

/**
 * Builds query with random or provided data
 *
 * @param {object} [data]
 * @param {string} [data.name]
 * @param {string} [data.text]
 * @param {boolean} [data.private]
 */
function buildQuery(data) {
  var id;
  id = QueryRepo.save({
    name: (data && data.name) || randomString(),
    text: (data && data.text) || randomString(),
    private: (data && data.private !== undefined && data.private) || false
  });
  return QueryRepo.get(id);
}

/**
 * Builds a list of queries with random parameters
 *
 * @param {number} cnt
 */
function buildQueries(cnt) {
  var i;
  var queries = [];
  for (i = 0; i < cnt; i++) {
    queries.push(buildQuery());
  }
}


describe('DjangoQL saved queries', function () {
  afterEach(function () {
    QueryRepo.objects = {};
  });

  describe('Fixtures', function () {
    describe('QueryRepository mock', function () {
      it('should generate ids', function () {
        expect(QueryRepo.generateId()).to.eql(1);
      });
      it('should create objects', function () {
        var query = buildQuery();
        QueryRepo.save(query, function (id) {
          var obj = QueryRepo.objects[id];
          expect(obj.name).to.eql(query.name);
          expect(obj.text).to.eql(query.text);
          expect(obj.id).to.be.a('number');
        });
      });

      it('should save objects', function () {
        var query = buildQuery();
        var changed = {
          id: query.id,
          name: 'changed',
          text: 'new query'
        };
        QueryRepo.save(changed, function (id) {
          var obj = QueryRepo.objects[id];
          expect(obj.id).to.eql(changed.id);
          expect(obj.name).to.eql(changed.name);
          expect(obj.text).to.eql(changed.text);
        });
      });

      it('should return list of objects', function () {
        buildQueries(10);
        QueryRepo.list(function (arr) {
          expect(arr).to.be.a('array');
          expect(arr.length).to.eql(10);
        });
      });

      it('should remove objects', function () {
        var query = buildQuery();
        QueryRepo.remove(query.id, function () {
          expect(Object.keys(QueryRepo.objects).length).to.eql(0);
        });
      });
    });

    describe('buildQuery', function () {
      it('should create query with random name and text', function () {
        var query = buildQuery();
        expect(query).to.be.a('object');
      });
    });
  });

  describe('Controller', function () {
    var controller;

    before(function () {
      controller = SavedQueries.init({
        view: new SavedQueries.View({
          formSelector: 'form',
          inputSelector: 'textarea',
          submitSelector: '[type="submit"]',
          buttonText: 'Saved queries'
        }),
        repo: QueryRepo,
        submitOnSelect: false
      });
      QueryRepo.objects = {};
    });

    describe('Initalization', function () {
      describe('constructor', function () {
        it('should create button', function () {
          var button = document.querySelector('.djangoql-sq-button');
          expect(button).to.be.an('object');
        });
        it('should create dialog', function () {
          var dialog = document.querySelector('.djangoql-sq-dialog');
          expect(dialog).to.be.an('object');
        });
        it('should create label', function () {
          var label = document.querySelector('.djangoql-sq-label');
          expect(label).to.be.an('object');
        });
      });

      describe('.saveAsNewQuery()', function () {
        it('should create new query', function () {
          document.querySelector('textarea').value = 'example';
          controller.saveAsNewQuery('test', false, function (id) {
            var query = QueryRepo.objects[id];
            document.querySelector('textarea').value = '';

            expect(query).to.be.an('object');
            expect(query.name).to.eql('test');
          });
        });
      });
    });

    describe('Working with existing query', function () {
      var query;

      beforeEach(function () {
        query = buildQuery();
      });

      describe('.saveAsCurrentQuery()', function () {
        it('should update current query text', function () {
          controller.currentQuery = query;
          document.querySelector('textarea').value = 'new';

          controller.saveAsCurrentQuery(null, function () {
            var obj = QueryRepo.get(query.id);
            document.querySelector('textarea').value = '';

            expect(obj).to.be.an('object');
            expect(obj.text).to.eql('new');
          });
        });
      });

      describe('.selectQuery()', function () {
        it('should insert text in search input', function () {
          controller.selectQuery(query);
          expect(document.querySelector('textarea').value).to.eql(query.text);
        });
      });

      describe('.changeQueryScope()', function () {
        it('should change private attribute of the query', function () {
          controller.changeQueryScope(query, function () {
            var result = QueryRepo.get(query.id);
            expect(result.private).to.eql(!query.private);
          });
        });
      });

      describe('.removeQuery()', function () {
        it('should remove query from collection', function () {
          controller.removeQuery(query, function () {
            expect(QueryRepo.get(query.id)).to.eql(undefined);
          });
        });
      });

      describe('.renameQuery()', function () {
        it('should change name attribute of the query', function () {
          controller.renameQuery(query, 'test', function () {
            expect(QueryRepo.get(query.id).name).to.eql('test');
          });
        });
      });

      describe('.resetCurrentQuery()', function () {
        it('should reset current query', function () {
          controller.selectQuery(query);
          expect(controller.currentQuery).to.be.an('object');
          controller.resetCurrentQuery();
          expect(controller.currentQuery).to.eql(null);
        });
      });
    });
  });
});
