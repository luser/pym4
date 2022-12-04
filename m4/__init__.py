#!/usr/bin/env python

import sys
from typing import Iterator, Optional, Union

from collections import defaultdict


__version__ = (0, 0, 1)


class ParseError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'ParseError(%s)' % self.message


class Token(object):
    def __init__(self, name: bytes, value: Optional[bytes] = None):
        self.type = name
        self.value = name if value is None else value

    def __eq__(self, other):
        if isinstance(other, Token):
            return self.type == other.type and self.value == other.value
        return False

    def __repr__(self):
        return "<Token: %r %r>" % (self.type, self.value)


class eof(str):
    def __repr__(self):
        return '<EOF>'


EOF = eof()


def name(x):
    return x.__name__ if hasattr(x, '__name__') else x


class peek_insert_iter:
    def __init__(self, iter):
        self.iter = iter
        self.inserted = bytearray()
        self.peeked = bytearray()

    def __iter__(self):
        return self

    def __next__(self):
        if self.inserted:
            return self.inserted.pop(0)
        if self.peeked:
            return self.peeked.pop(0)
        return next(self.iter)

    def insert(self, iterable: Union[bytes, eof]):
        self.inserted[0:0] = iterable

    def _peek(self):
        if not self.peeked:
            try:
                self.peeked.append(next(self.iter))
            except StopIteration:
                pass

    def peek(self) -> Union[int, eof]:
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
        self.chars = bytearray()
        self.nesting_level = 0
        self.start_quote = b'`'
        self.end_quote = b"'"
        self.iter = None

    def _finish_token(self, name):
        t = Token(name, bytes(self.chars))
        self.chars = bytearray()
        return t

    def insert_text(self, text):
        self.iter.insert(text)

    def changequote(self, start_quote=b'`', end_quote=b'\''):
        self.start_quote = start_quote
        self.end_quote = end_quote

    def parse(self):
        '''
        Return an iterator that produces tokens. The iterator
        has one extra method: peek_char, that allows consumers
        to peek at the next character before it is lexed.
        '''
        lexer = self

        class peekthrough_iter:
            def __init__(self, iter):
                self.iter = iter

            def __iter__(self) -> Token:
                return self.iter

            def __next__(self) -> Token:
                return next(self.iter)

            def peek_char(self) -> int:
                return lexer.iter.peek()
        self.iter = peek_insert_iter(iter(self.text))
        return peekthrough_iter(self._parse_internal())

    def _parse_internal(self) -> Iterator[Token]:
        while True:
            c = self.iter.peek()
            #print 'CHAR: %s (state: %s)' % (repr(c), name(self.state))
            if self.state is not None:
                tokens = self.state(c)
            else:
                tokens = self._generic(c)
            for tok in tokens:
                yield tok
            if c is EOF and self.iter.peek() is EOF:
                break
        if self.chars:
            if self.state is None:
                for c in self.chars:
                    yield Token(bytes([c]), bytes([c]))
            else:
                raise ParseError('Error, unterminated %s' % name(self.state))

    def _generic(self, c):
        if c is not EOF:
            self.chars.append(next(self.iter))
            if bytearray([c]).isalpha() or c == ord('_'):
                self.state = self._identifier
            elif c == ord('#'):
                self.state = self._comment
        # TODO: handle multi-character quotes
        if self.chars == self.start_quote:
            self.state = self._string
            self.nesting_level = 1
        if self.state is None:
            tokens = [Token(bytes([c]), bytes([c])) for c in self.chars]
            self.chars = bytearray()
            return tokens
        return []

    def _string(self, c):
        self.chars.append(next(self.iter))
        if (
                self.start_quote != self.end_quote and
                self.chars.endswith(self.start_quote)
        ):
            self.nesting_level += 1
        elif self.chars.endswith(self.end_quote):
            self.nesting_level -= 1
            if self.nesting_level == 0:
                # strip start/end quote out of the token value
                self.chars = \
                    self.chars[len(self.start_quote):-len(self.end_quote)]
                self.state = None
                return [self._finish_token('STRING')]
        return []

    def _identifier(self, c):
        if c is EOF or not (bytearray([c]).isalnum() or c == ord('_')):
            self.state = None
            return [self._finish_token('IDENTIFIER')]

        self.chars.append(next(self.iter))
        return []

    def _comment(self, c):
        if c != ord('\n') and c is not EOF:
            self.chars.append(next(self.iter))
            return []

        self.state = None
        return [self._finish_token('COMMENT')]


def substmacro(name, body, args):
    # TODO: implement argument substitution
    return body


class Parser:
    def __init__(self, text):
        self.macros = {
            b'define': self._builtin_define,
            b'dnl': self._builtin_dnl,
            b'changequote': self._builtin_changequote,
            b'divert': self._builtin_divert,
        }
        self.lexer = Lexer(text)
        self.token_iter = self.lexer.parse()
        self.diversions = defaultdict(list)
        self.current_diversion = 0

    def _builtin_define(self, args):
        if args:
            self.define(*args[:2])
        return None

    def _builtin_dnl(self, args):
        # Eat tokens till newline
        for tok in self.token_iter:
            if tok.value == b'\n':
                break
        return None

    def _builtin_changequote(self, args):
        self.changequote(*args[:2])
        return None

    def _builtin_divert(self, args):
        args = args or [0]
        try:
            self.current_diversion = int(args[0])
        except ValueError:
            # GNU m4 prints a warning here:
            # m4:stdin:1: non-numeric argument to builtin `divert'
            return
        return None

    def _parse_args(self):
        args = []
        current_arg = []
        if self.token_iter.peek_char() == ord('('):
            # drop that token
            tok = next(self.token_iter)
            if tok.value != b'(':
                raise ParseError('Expected open parenthesis but got %s'
                                 % tok.value)
            nesting_level = 1
            for tok in self._expand_tokens():
                if tok.value == b'(':
                    nesting_level += 1
                elif tok.value == b',' or tok.value == b')':
                    args.append(b''.join(current_arg))
                    current_arg = []
                elif current_arg or not tok.value.isspace():
                    current_arg.append(tok.value)
                if tok.value == b')':
                    nesting_level -= 1
                    if nesting_level == 0:
                        break
            # TODO: handle EOF without closing paren
        return args

    def _expand_tokens(self):
        for tok in self.token_iter:
            if (
                    isinstance(tok, Token)
                    and tok.type == 'IDENTIFIER'
                    and tok.value in self.macros
            ):
                result = self.macros[tok.value](self._parse_args())
                if result:
                    self.lexer.insert_text(result)
            else:
                yield tok

    def define(self, name, body=b''):
        self.macros[name] = lambda x: substmacro(name, body, x)

    def changequote(self, start_quote=b'`', end_quote=b'\''):
        self.lexer.changequote(start_quote, end_quote)

    def parse(self, stream=sys.stdout.buffer):
        for tok in self._expand_tokens():
            if self.current_diversion == 0:
                stream.write(tok.value)
            elif self.current_diversion > 0:
                self.diversions[self.current_diversion].append(tok.value)
        for diversion in sorted(self.diversions.keys()):
            if diversion < 1:
                continue
            stream.write(b''.join(self.diversions[diversion]))
            self.diversions[diversion] = []


if __name__ == '__main__':
    Parser(sys.stdin.buffer.read()).parse()
