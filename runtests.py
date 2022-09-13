#!/usr/bin/env python3

import glob
import os
import subprocess
import unittest
from io import BytesIO

from m4 import (
    peek_insert_iter,
    Lexer,
    Parser,
    Token,
    EOF,
)


class IterTests(unittest.TestCase):
    def test_insert(self):
        i = peek_insert_iter(iter([1, 2, 3]))
        i.insert([10])
        self.assertEqual(next(i), 10)
        self.assertEqual(next(i), 1)
        i.insert([4, 5])
        i.insert([6, 7])
        self.assertEqual(next(i), 6)
        self.assertEqual(next(i), 7)
        self.assertEqual(next(i), 4)
        self.assertEqual(next(i), 5)
        self.assertEqual(next(i), 2)
        self.assertEqual(next(i), 3)
        with self.assertRaises(StopIteration):
            next(i)
        i.insert([8])
        self.assertEqual(next(i), 8)
        with self.assertRaises(StopIteration):
            next(i)

    def test_peek(self):
        i = peek_insert_iter(iter([1, 2, 3]))
        self.assertEqual(i.peek(), 1)
        self.assertEqual(next(i), 1)
        self.assertEqual(i.peek(), 2)
        self.assertEqual(next(i), 2)
        self.assertEqual(i.peek(), 3)
        self.assertEqual(next(i), 3)
        self.assertIs(i.peek(), EOF)

    def test_peek_insert(self):
        i = peek_insert_iter(iter([1, 2, 3]))
        i.insert([10])
        self.assertEqual(i.peek(), 10)
        self.assertEqual(next(i), 10)
        self.assertEqual(i.peek(), 1)
        self.assertEqual(next(i), 1)
        i.insert([4, 5])
        self.assertEqual(i.peek(), 4)
        i.insert([6, 7])
        self.assertEqual(i.peek(), 6)
        self.assertEqual(next(i), 6)
        self.assertEqual(next(i), 7)
        self.assertEqual(next(i), 4)
        self.assertEqual(next(i), 5)
        self.assertEqual(next(i), 2)
        self.assertEqual(next(i), 3)
        self.assertIs(i.peek(), EOF)
        i.insert([8])
        self.assertEqual(i.peek(), 8)
        self.assertEqual(next(i), 8)
        self.assertIs(i.peek(), EOF)


class LexerTests(unittest.TestCase):
    def lex(self, text):
        return list(Lexer(text).parse())

    def test_basic(self):
        tokens = self.lex(b'abc xy_z _foo')
        self.assertEqual(tokens,
                         [Token('IDENTIFIER', b'abc'),
                          Token(b' '),
                          Token('IDENTIFIER', b'xy_z'),
                          Token(b' '),
                          Token('IDENTIFIER', b'_foo')])
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, b'abc')
        self.assertEqual(tokens[1].value, b' ')
        self.assertEqual(self.lex(b'_abc123 123'),
                         [Token('IDENTIFIER', b'_abc123'),
                          Token(b' '),
                          Token(b'1'),
                          Token(b'2'),
                          Token(b'3')])

        tokens = self.lex(b'1abc')
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0], Token(b'1'))
        self.assertEqual(tokens[1].type, 'IDENTIFIER')
        self.assertEqual(tokens[1].value, b'abc')

        text = b'([{}])=+-,.?/|\n'
        self.assertEqual(self.lex(text), [Token(bytes([c])) for c in text])

    def test_strings(self):
        tokens = self.lex(b"`'")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, b'')

        tokens = self.lex(b"`abc'")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, b'abc')

        tokens = self.lex(b"foo`abc'foo")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, b'foo')
        self.assertEqual(tokens[1].type, 'STRING')
        self.assertEqual(tokens[1].value, b'abc')
        self.assertEqual(tokens[2].type, 'IDENTIFIER')
        self.assertEqual(tokens[2].value, b'foo')

        tokens = self.lex(b"`foo' `foo'")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, b'foo')
        self.assertEqual(tokens[1], Token(b' '))
        self.assertEqual(tokens[2].type, 'STRING')
        self.assertEqual(tokens[2].value, b'foo')

        tokens = self.lex(b"`foo'`foo'")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, b'foo')
        self.assertEqual(tokens[1].type, 'STRING')
        self.assertEqual(tokens[1].value, b'foo')

    def test_nested_quotes(self):
        tokens = self.lex(b"`abc `xyz' abc'")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, b"abc `xyz' abc")

    def test_changequote(self):
        lex = Lexer(b"`abc'`abc'[xyz]`abc'")
        i = lex.parse()
        token = next(i)
        self.assertEqual(token.type, 'STRING')
        self.assertEqual(token.value, b'abc')
        lex.changequote(b'[', b']')
        # changing the quote characters should make the default quote
        # characters be treated as normal characters.
        token = next(i)
        self.assertEqual(token, Token(b'`'))
        token = next(i)
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, b'abc')
        token = next(i)
        self.assertEqual(token, Token(b'\''))
        # ...and the new quote characters should work
        token = next(i)
        self.assertEqual(token.type, 'STRING')
        self.assertEqual(token.value, b'xyz')
        # check that the defaults work
        lex.changequote()
        token = next(i)
        self.assertEqual(token.type, 'STRING')
        self.assertEqual(token.value, b'abc')

    def test_comments(self):
        tokens = self.lex(b"# foo")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'COMMENT')
        self.assertEqual(tokens[0].value, b'# foo')

        tokens = self.lex(b"foo # foo")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, b'foo')
        self.assertEqual(tokens[1], Token(b' '))
        self.assertEqual(tokens[2].type, 'COMMENT')
        self.assertEqual(tokens[2].value, b'# foo')

        tokens = self.lex(b"foo#foo")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, b'foo')
        self.assertEqual(tokens[1].type, 'COMMENT')
        self.assertEqual(tokens[1].value, b'#foo')

        tokens = self.lex(b"foo#foo\nfoo")
        self.assertEqual(len(tokens), 4)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, b'foo')
        self.assertEqual(tokens[1].type, 'COMMENT')
        self.assertEqual(tokens[1].value, b'#foo')
        self.assertEqual(tokens[2], Token(b'\n'))
        self.assertEqual(tokens[3].type, 'IDENTIFIER')
        self.assertEqual(tokens[3].value, b'foo')

    def test_insert(self):
        lex = Lexer(b'abc xyz')
        i = lex.parse()
        token = next(i)
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, b'abc')
        lex.insert_text(b'foo')
        token = next(i)
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, b'foo')
        token = next(i)
        self.assertEqual(token, Token(b' '))
        token = next(i)
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, b'xyz')

    def test_insert_eof(self):
        lex = Lexer(b'abc')
        i = lex.parse()
        token = next(i)
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, b'abc')
        lex.insert_text(b'foo')
        token = next(i)
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, b'foo')

    def test_peek_char(self):
        lex = Lexer(b'abc xyz')
        i = lex.parse()
        self.assertEqual(i.peek_char(), ord('a'))
        token = next(i)
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, b'abc')
        self.assertEqual(i.peek_char(), ord(' '))
        token = next(i)
        self.assertEqual(token, Token(b' '))
        self.assertEqual(i.peek_char(), ord('x'))
        token = next(i)
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, b'xyz')
        self.assertIs(i.peek_char(), EOF)


class ParserTests(unittest.TestCase):
    def parse(self, parser):
        stream = BytesIO()
        parser.parse(stream=stream)
        return stream.getvalue()

    def test_basic(self):
        p = Parser(b'abc')
        self.assertEqual(self.parse(p), b'abc')

    def test_empty_string(self):
        p = Parser(b"`'")
        self.assertEqual(self.parse(p), b'')

    def test_define_empty(self):
        p = Parser(b'abc')
        p.define(b'abc')
        self.assertEqual(self.parse(p), b'')

    def test_define_simple(self):
        p = Parser(b'abc')
        p.define(b'abc', b'xyz')
        self.assertEqual(self.parse(p), b'xyz')

    def test_define_simple_trailing(self):
        p = Parser(b'abc ')
        p.define(b'abc', b'xyz')
        self.assertEqual(self.parse(p), b'xyz ')

    def test_define_recursive(self):
        p = Parser(b'abc')
        p.define(b'abc', b'xyz')
        p.define(b'xyz', b'123')
        self.assertEqual(self.parse(p), b'123')

    def test_define_argparse(self):
        p = Parser(b'define( abc, xyz)abc')
        self.assertEqual(self.parse(p), b'xyz')

    def test_changequote(self):
        p = Parser(b"`abc'[xyz]")
        p.changequote(b'[', b']')
        self.assertEqual(self.parse(p), b"`abc'xyz")

    def test_macro_args_nested_parens(self):
        p = Parser(b'foo(abc(xyz)abc)')
        p.define(b'foo', b'bar')
        self.assertEqual(self.parse(p), b'bar')


class ComparisonTests(unittest.TestCase):
    def check_file(self, input_file, expected_file, thing):
        with open(expected_file, 'rb') as f:
            expected = f.read()
        if thing == 'm4':
            # check m4 output
            m4_output = subprocess.check_output(['m4', input_file])
            self.assertEqual(m4_output, expected)
        elif thing == 'parser':
            stream = BytesIO()
            with open(input_file, 'rb') as f:
                Parser(f.read()).parse(stream=stream)
                self.assertEqual(stream.getvalue(), expected)


def create_test(input_file, output_file, thing):
    with open(input_file, 'rb') as f:
        first_line = f.readline()
    def do_test(self):
        self.check_file(input_file, output_file, thing)
    if first_line.startswith(b'dnl fail') and thing == 'parser':
        return unittest.expectedFailure(do_test)
    return do_test


def basename(file):
    return os.path.splitext(os.path.basename(file))[0]


def setup_comparison_tests():
    test_dir = os.path.join(os.path.dirname(__file__), 'test')
    for input_file in glob.glob(os.path.join(test_dir, '*.in')):
        output_file = os.path.splitext(input_file)[0] + '.out'
        for thing in ('m4', 'parser'):
            test_method = create_test(input_file, output_file, thing)
            test_method.__name__ = 'test_file_%s_%s' % (basename(input_file),
                                                        thing)
            setattr(ComparisonTests, test_method.__name__, test_method)

if __name__ == '__main__':
    setup_comparison_tests()
    unittest.main()
