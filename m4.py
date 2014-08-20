#!/usr/bin/env python

import itertools
import sys


class ParseError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'ParseError(%s)' % self.message


class Token(object):
    def __init__(self, name, value):
        self.type = name
        self.value = value

    def __eq__(self, other):
        if isinstance(other, Token):
            return self.type == other.type and self.value == other.value
        elif isinstance(other, basestring):
            return self.value == other
        return False

    def __repr__(self):
        return "<Token: %r %r>" % (self.type, self.value)


class eof(str):
    def __repr__(self):
        return '<EOF>'


EOF = eof()


def endswith(l, e):
    return l[-len(e):] == e


def name(x):
    return x.__name__ if hasattr(x, '__name__') else x


class peek_insert_iter:
    def __init__(self, iter):
        self.iter = iter
        self.inserted = []
        self.peeked = []

    def __iter__(self):
        return self

    def next(self):
        if self.inserted:
            return self.inserted.pop(0)
        if self.peeked:
            return self.peeked.pop(0)
        return self.iter.next()

    def insert(self, iterable):
        self.inserted[0:0] = iterable

    def _peek(self):
        if not self.peeked:
            try:
                self.peeked.append(self.iter.next())
            except StopIteration:
                pass

    def peek(self):
        if self.inserted:
            return self.inserted[0]
        self._peek()
        if self.peeked:
            return self.peeked[0]
        return EOF


class Lexer:
    def __init__(self, text):
        self.text = text
        self.state = None
        self.chars = []
        self.start_quote = ['`']
        self.end_quote = ["'"]
        self.iter = None

    def _finish_token(self, name):
        t = Token(name, ''.join(self.chars))
        self.chars = []
        return t

    def insert_text(self, text):
        self.iter.insert(text)

    def parse(self):
        self.iter = peek_insert_iter(iter(self.text))
        while True:
            c = self.iter.peek()
            #print 'CHAR: %s (state: %s)' % (repr(c), name(self.state))
            if self.state is not None:
                tokens = self.state(c)
            else:
                tokens = self._generic(c)
            for tok in tokens:
                yield tok
            if c is EOF:
                break
        if self.chars:
            if self.state is None:
                for c in self.chars:
                    yield c
            else:
                raise ParseError('Error, unterminated %s' % name(self.state))

    def _generic(self, c):
        if c is not EOF:
            self.chars.append(self.iter.next())
        if c.isalpha() or c == '_':
            self.state = self._identifier
        elif c == '#':
            self.state = self._comment
        # TODO: handle multi-character quotes
        if self.chars == self.start_quote:
            self.state = self._string
        if self.state is None:
            chars = self.chars
            self.chars = []
            return chars
        return []

    def _string(self, c):
        self.chars.append(self.iter.next())
        if endswith(self.chars, self.end_quote):
            # strip start/end quote out of the token value
            self.chars = self.chars[len(self.start_quote):-len(self.end_quote)]
            self.state = None
            return [self._finish_token('STRING')]
        return []

    def _identifier(self, c):
        if not (c.isalnum() or c == '_'):
            self.state = None
            return [self._finish_token('IDENTIFIER')]

        self.chars.append(self.iter.next())
        return []

    def _comment(self, c):
        if c != '\n' and c is not EOF:
            self.chars.append(self.iter.next())
            return []

        self.state = None
        return [self._finish_token('COMMENT')]


def substmacro(name, body, args):
    # TODO: implement argument substitution
    return body


def tokvalue(tok):
    return tok.value if isinstance(tok, Token) else tok


class Parser:
    def __init__(self, text):
        self.macros = {
            'define': self.define,
            'dnl': self.dnl,
            # TODO: changequote
        }
        self.lexer = Lexer(text)
        self.token_iter = peek_insert_iter(self.lexer.parse())

    def define(self, args):
        if args:
            name = args[0]
            if len(args) >= 2:
                body = args[1]
            else:
                body = ''
            self.macros[name] = lambda x: substmacro(name, body, x)
        return None

    def dnl(self, args):
        # Eat tokens till newline
        for tok in self.token_iter:
            if tok == '\n':
                break
        return None

    def _parse_args(self):
        tok = self.token_iter.peek()
        args = []
        current_arg = []
        if tok == '(':
            # drop that token
            self.token_iter.next()
            for tok in self.expand_tokens():
                if tok == ',' or tok == ')':
                    args.append(''.join(current_arg))
                    current_arg = []
                else:
                    current_arg.append(tokvalue(tok))
                if tok == ')':
                    break
        return args

    def expand_tokens(self):
        for tok in self.token_iter:
            if (
                    isinstance(tok, Token)
                    and tok.type == 'IDENTIFIER'
                    and tok.value in self.macros
            ):
                result = self.macros[tok.value](self._parse_args())
                if result:
                    # TODO: push back
                    pass
            else:
                yield tok

    def parse(self, stream=sys.stdout):
        for tok in self.expand_tokens():
            stream.write(tokvalue(tok))


if __name__ == '__main__':
    Parser(sys.stdin.read()).parse()
