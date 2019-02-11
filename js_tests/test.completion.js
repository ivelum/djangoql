'use strict';

/* global DjangoQL, expect, describe, before, it */

var djangoQL;
var token;

describe('DjangoQL completion', function () {
  before(function () {
    djangoQL = new DjangoQL({
      introspections: {
        current_model: 'core.book',
        models: {
          'auth.group': {
            user: {
              type: 'relation',
              relation: 'auth.user'
            },
            id: {
              type: 'int',
              relation: null
            },
            name: {
              type: 'str',
              relation: null
            }
          },
          'auth.user': {
            book: {
              type: 'relation',
              relation: 'core.book'
            },
            id: {
              type: 'int',
              relation: null
            },
            password: {
              type: 'str',
              relation: null
            },
            last_login: {
              type: 'datetime',
              relation: null
            },
            is_superuser: {
              type: 'bool',
              relation: null
            },
            username: {
              type: 'str',
              relation: null
            },
            first_name: {
              type: 'str',
              relation: null
            },
            last_name: {
              type: 'str',
              relation: null
            },
            email: {
              type: 'str',
              relation: null
            },
            is_staff: {
              type: 'bool',
              relation: null
            },
            is_active: {
              type: 'bool',
              relation: null
            },
            date_joined: {
              type: 'datetime',
              relation: null
            },
            groups: {
              type: 'relation',
              relation: 'auth.group'
            }
          },
          'core.book': {
            id: {
              type: 'int',
              relation: null
            },
            name: {
              type: 'str',
              relation: null
            },
            author: {
              type: 'relation',
              relation: 'auth.user'
            },
            written: {
              type: 'datetime',
              relation: null
            },
            is_published: {
              type: 'bool',
              relation: null
            },
            rating: {
              type: 'float',
              relation: null
            },
            price: {
              type: 'float',
              relation: null
            }
          }
        }
      },
      selector: 'textarea[name=test]',
      autoresize: true
    });
    token = djangoQL.token;
  });

  describe('.init()', function () {
    it('should properly read introspection data', function () {
      expect(djangoQL.currentModel).to.be('core.book');
    });
  });

  describe('.lexer', function () {
    it('should understand punctuation and ignore white space', function () {
      var tokens = [
        token('PAREN_L', '('),
        token('PAREN_R', ')'),
        token('DOT', '.'),
        token('COMMA', ','),
        token('EQUALS', '='),
        token('NOT_EQUALS', '!='),
        token('GREATER', '>'),
        token('GREATER_EQUAL', '>='),
        token('LESS', '<'),
        token('LESS_EQUAL', '<='),
        token('CONTAINS', '~'),
        token('NOT_CONTAINS', '!~')
      ];
      djangoQL.lexer.setInput('() ., = != >\t >= < <= ~ !~');
      tokens.forEach(function (t) {
        expect(djangoQL.lexer.lex()).to.eql(t);
      });
      expect(djangoQL.lexer.lex()).to.not.be.ok();  // end of input
    });

    it('should recognize names', function () {
      var names = ['a', 'myVar_42', '__LOL__', '_', '_0'];
      djangoQL.lexer.setInput(names.join(' '));
      names.forEach(function (name) {
        expect(djangoQL.lexer.lex()).to.eql(token('NAME', name));
      });
    });

    it('should recognize reserved words', function () {
      var words = ['True', 'False', 'None', 'or', 'and', 'in'];
      djangoQL.lexer.setInput(words.join(' '));
      words.forEach(function (word) {
        expect(djangoQL.lexer.lex()).to.eql(token(word.toUpperCase(), word));
      });
    });

    it('should recognize strings', function () {
      var strings = ['""', '"42"', '"\\t\\n\\u0042 \\" ^"'];
      djangoQL.lexer.setInput(strings.join(' '));
      strings.forEach(function (s) {
        expect(djangoQL.lexer.lex()).to
            .eql(token('STRING_VALUE', s.slice(1, s.length - 1)));
      });
    });

    it('should parse int values', function () {
      var numbers = ['0', '-0', '42', '-42'];
      djangoQL.lexer.setInput(numbers.join(' '));
      numbers.forEach(function (num) {
        expect(djangoQL.lexer.lex()).to.eql(token('INT_VALUE', num));
      });
    });

    it('should parse float values', function () {
      var numbers = ['-0.5e+42', '42.0', '2E64', '2.71e-0002'];
      djangoQL.lexer.setInput(numbers.join(' '));
      numbers.forEach(function (num) {
        expect(djangoQL.lexer.lex()).to.eql(token('FLOAT_VALUE', num));
      });
    });
  });

  describe('.resolveName()', function () {
    it('should properly resolve known names', function () {
      expect(djangoQL.resolveName('price')).to
          .eql({ model: 'core.book', field: 'price' });
      expect(djangoQL.resolveName('author')).to
          .eql({ model: 'auth.user', field: null });
      expect(djangoQL.resolveName('author.first_name')).to
          .eql({ model: 'auth.user', field: 'first_name' });
      expect(djangoQL.resolveName('author.groups')).to
          .eql({ model: 'auth.group', field: null });
      expect(djangoQL.resolveName('author.groups.id')).to
          .eql({ model: 'auth.group', field: 'id' });
      expect(djangoQL.resolveName('author.groups.user')).to
          .eql({ model: 'auth.user', field: null });
      expect(djangoQL.resolveName('author.groups.user.email')).to
          .eql({ model: 'auth.user', field: 'email' });
    });
    it('should return nulls for unknown names', function () {
      ['gav', 'author.gav', 'author.groups.gav'].forEach(function (name) {
        expect(djangoQL.resolveName(name)).to.eql({ model: null, field: null });
      });
    });
  });

  describe('.getScope()', function () {
    it('should properly detect scope and prefix', function () {
      var book = djangoQL.currentModel;
      var examples = [
        {
          args: ['', 0],
          result: { prefix: '', scope: 'field', model: book, field: null }
        },
        {
          args: ['just some text after cursor', 0],
          result: { prefix: '', scope: 'field', model: book, field: null }
        },
        {
          args: ['random_word', 4],  // cursor is at the end of word
          result: { prefix: 'rand', scope: 'field', model: book, field: null }
        },
        {
          args: ['random', 6],  // cursor is at the end of word
          result: { prefix: 'random', scope: 'field', model: book, field: null }
        },
        {
          args: ['id', 2],  // cursor is at the end of known field
          result: { prefix: 'id', scope: 'field', model: book, field: null }
        },
        {
          args: ['id ', 3],  // cursor is after known field
          result: { prefix: '', scope: 'comparison', model: book, field: 'id' }
        },
        {
          args: ['id >', 4],  // cursor is at the end of comparison
          result: { prefix: '>', scope: 'comparison', model: book, field: 'id' }
        },
        {
          args: ['id > ', 5],  // cursor is after comparison
          result: { prefix: '', scope: 'value', model: book, field: 'id' }
        },
        {
          args: ['id > 1', 6],  // entering value
          result: { prefix: '1', scope: 'value', model: book, field: 'id' }
        },
        {
          args: ['id > 1 ', 7],  // cursor is after value
          result: { prefix: '', scope: 'logical', model: null, field: null }
        },
        {
          args: ['id > 1 hmm', 10],  // entering logical
          result: { prefix: 'hmm', scope: 'logical', model: null, field: null }
        },
        {
          args: ['id > 1 and ', 11],  // entered good logical
          result: { prefix: '', scope: 'field', model: book, field: null }
        },
        {
          args: ['id > 1 and author.', 18],  // referencing related model
          result: {
            prefix: '',
            scope: 'field',
            model: 'auth.user',
            field: null
          }
        },
        {
          args: ['id > 1 and author.i', 19],  // typing field of related model
          result: {
            prefix: 'i',
            scope: 'field',
            model: 'auth.user',
            field: null
          }
        },
        {
          args: ['(id = 1) ', 9],  // cursor is after right paren and space
          result: { prefix: '', scope: 'logical', model: null, field: null }
        },
        {
          args: ['(id = 1) a', 10],  // typing after right paren
          result: { prefix: 'a', scope: 'logical', model: null, field: null }
        },
        {
          args: ['(id = 1)', 1],  // cursor is right after left paren
          result: { prefix: '', scope: 'field', model: book, field: null }
        },
        {
          args: ['(id = 1)', 2],  // cursor is 1 symbol after left paren
          result: { prefix: 'i', scope: 'field', model: book, field: null }
        }
      ];
      examples.forEach(function (e) {
        expect(djangoQL.getContext.apply(djangoQL, e.args)).to.eql(e.result);
      });
    });

    it('should return nulls for unknown cases', function () {
      var examples = [
        ['random_word ', 12],  // cursor is after unknown field
        ['id > 1 hmm ', 11],  // entered bad logical
        ['(id = 1)', 8],  // just after right paren
        ['a = "', 5]  // just after a quote
      ];
      examples.forEach(function (example) {
        var context = djangoQL.getContext.apply(djangoQL, example);
        expect(context.scope).to.be(null);
        expect(context.model).to.be(null);
        expect(context.field).to.be(null);
      });
    });
  });
});
