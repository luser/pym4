#!/usr/bin/env python

import glob
import os
import subprocess
import unittest
from io import StringIO

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
        self.assertEqual(i.next(), 10)
        self.assertEqual(i.next(), 1)
        i.insert([4, 5])
        i.insert([6, 7])
        self.assertEqual(i.next(), 6)
        self.assertEqual(i.next(), 7)
        self.assertEqual(i.next(), 4)
        self.assertEqual(i.next(), 5)
        self.assertEqual(i.next(), 2)
        self.assertEqual(i.next(), 3)
        with self.assertRaises(StopIteration):
            i.next()
        i.insert([8])
        self.assertEqual(i.next(), 8)
        with self.assertRaises(StopIteration):
            i.next()

    def test_peek(self):
        i = peek_insert_iter(iter([1, 2, 3]))
        self.assertEqual(i.peek(), 1)
        self.assertEqual(i.next(), 1)
        self.assertEqual(i.peek(), 2)
        self.assertEqual(i.next(), 2)
        self.assertEqual(i.peek(), 3)
        self.assertEqual(i.next(), 3)
        self.assertIs(i.peek(), EOF)

    def test_peek_insert(self):
        i = peek_insert_iter(iter([1, 2, 3]))
        i.insert([10])
        self.assertEqual(i.peek(), 10)
        self.assertEqual(i.next(), 10)
        self.assertEqual(i.peek(), 1)
        self.assertEqual(i.next(), 1)
        i.insert([4, 5])
        self.assertEqual(i.peek(), 4)
        i.insert([6, 7])
        self.assertEqual(i.peek(), 6)
        self.assertEqual(i.next(), 6)
        self.assertEqual(i.next(), 7)
        self.assertEqual(i.next(), 4)
        self.assertEqual(i.next(), 5)
        self.assertEqual(i.next(), 2)
        self.assertEqual(i.next(), 3)
        self.assertIs(i.peek(), EOF)
        i.insert([8])
        self.assertEqual(i.peek(), 8)
        self.assertEqual(i.next(), 8)
        self.assertIs(i.peek(), EOF)


class LexerTests(unittest.TestCase):
    def lex(self, text):
        return list(Lexer(text).parse())

    def test_basic(self):
        tokens = self.lex('abc xy_z _foo')
        self.assertEqual(tokens,
                         [Token('IDENTIFIER', 'abc'),
                          Token(' '),
                          Token('IDENTIFIER', 'xy_z'),
                          Token(' '),
                          Token('IDENTIFIER', '_foo')])
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, 'abc')
        self.assertEqual(tokens[1].value, ' ')
        self.assertEqual(self.lex('_abc123 123'),
                         [Token('IDENTIFIER', '_abc123'),
                          Token(' '),
                          Token('1'),
                          Token('2'),
                          Token('3')])

        tokens = self.lex('1abc')
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0], Token('1'))
        self.assertEqual(tokens[1].type, 'IDENTIFIER')
        self.assertEqual(tokens[1].value, 'abc')

        text = '([{}])=+-,.?/|\n'
        self.assertEqual(self.lex(text), [Token(c) for c in text])

    def test_strings(self):
        tokens = self.lex("`'")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, '')

        tokens = self.lex("`abc'")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, 'abc')

        tokens = self.lex("foo`abc'foo")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, 'foo')
        self.assertEqual(tokens[1].type, 'STRING')
        self.assertEqual(tokens[1].value, 'abc')
        self.assertEqual(tokens[2].type, 'IDENTIFIER')
        self.assertEqual(tokens[2].value, 'foo')

        tokens = self.lex("`foo' `foo'")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, 'foo')
        self.assertEqual(tokens[1], Token(' '))
        self.assertEqual(tokens[2].type, 'STRING')
        self.assertEqual(tokens[2].value, 'foo')

        tokens = self.lex("`foo'`foo'")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, 'foo')
        self.assertEqual(tokens[1].type, 'STRING')
        self.assertEqual(tokens[1].value, 'foo')

    def test_nested_quotes(self):
        tokens = self.lex("`abc `xyz' abc'")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, "abc `xyz' abc")

    def test_changequote(self):
        lex = Lexer("`abc'`abc'[xyz]`abc'")
        i = lex.parse()
        token = i.next()
        self.assertEqual(token.type, 'STRING')
        self.assertEqual(token.value, 'abc')
        lex.changequote('[', ']')
        # changing the quote characters should make the default quote
        # characters be treated as normal characters.
        token = i.next()
        self.assertEqual(token, Token('`'))
        token = i.next()
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, 'abc')
        token = i.next()
        self.assertEqual(token, Token('\''))
        # ...and the new quote characters should work
        token = i.next()
        self.assertEqual(token.type, 'STRING')
        self.assertEqual(token.value, 'xyz')
        # check that the defaults work
        lex.changequote()
        token = i.next()
        self.assertEqual(token.type, 'STRING')
        self.assertEqual(token.value, 'abc')

    def test_comments(self):
        tokens = self.lex("# foo")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'COMMENT')
        self.assertEqual(tokens[0].value, '# foo')

        tokens = self.lex("foo # foo")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, 'foo')
        self.assertEqual(tokens[1], Token(' '))
        self.assertEqual(tokens[2].type, 'COMMENT')
        self.assertEqual(tokens[2].value, '# foo')

        tokens = self.lex("foo#foo")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, 'foo')
        self.assertEqual(tokens[1].type, 'COMMENT')
        self.assertEqual(tokens[1].value, '#foo')

        tokens = self.lex("foo#foo\nfoo")
        self.assertEqual(len(tokens), 4)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, 'foo')
        self.assertEqual(tokens[1].type, 'COMMENT')
        self.assertEqual(tokens[1].value, '#foo')
        self.assertEqual(tokens[2], Token('\n'))
        self.assertEqual(tokens[3].type, 'IDENTIFIER')
        self.assertEqual(tokens[3].value, 'foo')

    def test_insert(self):
        lex = Lexer('abc xyz')
        i = lex.parse()
        token = i.next()
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, 'abc')
        lex.insert_text('foo')
        token = i.next()
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, 'foo')
        token = i.next()
        self.assertEqual(token, Token(' '))
        token = i.next()
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, 'xyz')

    def test_insert_eof(self):
        lex = Lexer('abc')
        i = lex.parse()
        token = i.next()
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, 'abc')
        lex.insert_text('foo')
        token = i.next()
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, 'foo')

    def test_peek_char(self):
        lex = Lexer('abc xyz')
        i = lex.parse()
        self.assertEqual(i.peek_char(), 'a')
        token = i.next()
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, 'abc')
        self.assertEqual(i.peek_char(), ' ')
        token = i.next()
        self.assertEqual(token, Token(' '))
        self.assertEqual(i.peek_char(), 'x')
        token = i.next()
        self.assertEqual(token.type, 'IDENTIFIER')
        self.assertEqual(token.value, 'xyz')
        self.assertIs(i.peek_char(), EOF)


class ParserTests(unittest.TestCase):
    def parse(self, parser):
        stream = StringIO()
        parser.parse(stream=stream)
        return stream.getvalue()

    def test_basic(self):
        p = Parser('abc')
        self.assertEqual(self.parse(p), 'abc')

    def test_empty_string(self):
        p = Parser("`'")
        self.assertEqual(self.parse(p), '')

    def test_define_empty(self):
        p = Parser('abc')
        p.define('abc')
        self.assertEqual(self.parse(p), '')

    def test_define_simple(self):
        p = Parser('abc')
        p.define('abc', 'xyz')
        self.assertEqual(self.parse(p), 'xyz')

    def test_define_simple_trailing(self):
        p = Parser('abc ')
        p.define('abc', 'xyz')
        self.assertEqual(self.parse(p), 'xyz ')

    def test_define_recursive(self):
        p = Parser('abc')
        p.define('abc', 'xyz')
        p.define('xyz', '123')
        self.assertEqual(self.parse(p), '123')

    def test_define_argparse(self):
        p = Parser('define( abc, xyz)abc')
        self.assertEqual(self.parse(p), 'xyz')

    def test_changequote(self):
        p = Parser("`abc'[xyz]")
        p.changequote('[', ']')
        self.assertEqual(self.parse(p), "`abc'xyz")

    def test_macro_args_nested_parens(self):
        p = Parser('foo(abc(xyz)abc)')
        p.define('foo', 'bar')
        self.assertEqual(self.parse(p), 'bar')


class ComparisonTests(unittest.TestCase):
    def check_file(self, input_file, expected_file, thing):
        with open(expected_file, 'r') as f:
            expected = f.read()
        if thing == 'm4':
            # check m4 output
            m4_output = subprocess.check_output(['m4', input_file]).decode()
            self.assertEqual(m4_output, expected)
        elif thing == 'parser':
            with open(input_file, 'r') as f:
                inp = f.read()
            stream = StringIO()
            Parser(inp).parse(stream=stream)
            self.assertEqual(stream.getvalue(), expected)


def create_test(input_file, output_file, thing):
    first_line = open(input_file, 'r').readline()
    def do_test(self):
        self.check_file(input_file, output_file, thing)
    if first_line.startswith('dnl fail') and thing == 'parser':
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
