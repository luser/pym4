#!/usr/bin/env python

import itertools
import sys

class ParseError(Exception):
    def __init__(self, message):
        self.message = message

class Token(object):
    def __init__(self, name, value, lexpos, lineno):
        self.type = name
        self.value = value
        self.lexpos = lexpos
        self.lineno = lineno

    def __repr__(self):
        return "<Token: %r %r>" % (self.type, self.value)

class eof(str):
    def __repr__(self):
        return '<EOF>'
EOF = eof()

def endswith(l, e):
    return l[-len(e):] == e

def rmend(l, e):
    return l[:-len(e)]

def name(x):
    return x.__name__ if hasattr(x, '__name__') else x

keywords = {
    '(': 'LPAREN',
    ')': 'RPAREN',
    ',': 'COMMA',
    '\n': 'NEWLINE',
}

class Lexer:
    def __init__(self, text):
        self.text = text
        self.state = None
        self.lexpos = 0
        self.lineno = 0
        self.chars = []
        self.start_quote = ['`']
        self.end_quote = ["'"]

    def finish_token(self, name):
        t = Token(name, ''.join(self.chars), self.lexpos, self.lineno) if self.chars else None
        self.chars = []
        return t

    def parse(self):
        for i, c in enumerate(itertools.chain(self.text, [EOF])):
            self.lexpos = i
            if c == '\n':
                self.lineno += 1
            #print 'CHAR: %s (state: %s)' % (repr(c), name(self.state))
            tok, consumed = (None, False)
            while not consumed:
                if self.state is not None:
                    res = self.state(c)
                else:
                    res = self.generic(c)
                if res:
                    tok, consumed = res
                    if tok is not None:
                        yield tok
                if c is EOF:
                    break
        if self.chars:
            if self.state is None:
                yield self.finish_token('OTHER')
            else:
                raise ParseError('Error, unterminated %s' % self.state)

    def generic(self, c):
        t = None
        if c in keywords:
            return Token(keywords[c], c, self.lexpos, self.lineno), True
        if c.isalpha() or c == '_':
            t = self.finish_token('OTHER'), False
            self.state = self.identifier
        elif c == '#':
            t = self.finish_token('OTHER'), False
            self.state = self.comment
        else:
            self.chars.append(c)
            t = None, True
        if endswith(self.chars, self.start_quote):
            self.chars = rmend(self.chars, self.start_quote)
            t = self.finish_token('OTHER'), True
            self.state = self.string
        return t

    def string(self, c):
        self.chars.append(c)
        t = None
        if endswith(self.chars, self.end_quote):
            self.chars = rmend(self.chars, self.end_quote)
            self.state = None
            t = self.finish_token('STRING')
        return t, True

    def identifier(self, c):
        if not (c.isalnum() or c == '_'):
            self.state = None
            return self.finish_token('IDENTIFIER'), False

        self.chars.append(c)
        return None, True

    def comment(self, c):
        if c is not EOF:
            self.chars.append(c)
        if c == '\n' or c == EOF:
            self.state = None
            return self.finish_token('COMMENT'), True
        return None, True

class PLYCompatLexer(object):
    def __init__(self, text):
        self.text = text
        self.token_stream = Lexer(text).parse()

    def token(self):
        try:
            return self.token_stream.next()
        except StopIteration:
            return None

class peekiter:
    EOF = EOF
    def __init__(self, iter):
        self.iter = iter
        self.done = False
        self._peek()

    def __iter__(self):
        return self

    def next(self):
        if self.done:
            raise StopIteration
        n = self._next
        self._peek()
        return n

    def _peek(self):
        try:
            self._next = self.iter.next()
        except StopIteration:
            self.done = True

    def peek(self):
        if self.done:
            return self.EOF
        return self._next

class Parser:
    def __init__(self, text):
        self.macros = {
            'define': self.define,
            'dnl': self.dnl,
        }
        self.lexer = Lexer(text)
        self.token_iter = peekiter(self.lexer.parse())

    def define(self, args):
        if len(args) >= 2:
            self.macros[args[0]] = args[1]

    def dnl(self, args):
        # Eat tokens till newline
        for tok in self.token_iter:
            if tok.value == 'NEWLINE':
                break

    def _parse_args(self):
        tok = self.token_iter.peek()
        if tok is not peekiter.EOF and tok.value == 'LPAREN':
            #TODO: parse args
            return []
        else:
            return []

    def parse(self, stream=sys.stdout, verbose=False):
        for tok in self.token_iter:
            if verbose:
                print tok
            else:
                if tok.type == 'IDENTIFIER' and tok.value in self.macros:
                    self.macros[tok.value](self._parse_args())
                else:
                    stream.write(tok.value)

if __name__ == '__main__':
    verbose = sys.argv[-1] == '-v'
    Parser(sys.stdin.read()).parse(verbose=verbose)
