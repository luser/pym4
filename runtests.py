#!/usr/bin/env python

import glob
import os
import subprocess
import unittest
from StringIO import StringIO

from m4 import (
    Lexer,
    Parser,
    EOF,
)

class LexerTests(unittest.TestCase):
    def lex(self, text):
        return list(Lexer(text).parse())

    def test_basic(self):
        tokens = self.lex('abc xy_z _foo')
        self.assertEqual(tokens,
                         ['abc', ' ', 'xy_z', ' ', '_foo'])
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, 'abc')
        self.assertEqual(tokens[1], ' ')
        self.assertTrue(isinstance(tokens[1], basestring))
        self.assertEqual(self.lex('_abc123 123'),
                         ['_abc123', ' ', '1', '2', '3'])

        tokens = self.lex('1abc')
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0], '1')
        self.assertEqual(tokens[1].type, 'IDENTIFIER')
        self.assertEqual(tokens[1].value, 'abc')

        text = '([{}])=+-,.?/|\n'
        self.assertEqual(self.lex(text), list(text))


    def test_strings(self):
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
        self.assertEqual(tokens[1], ' ')
        self.assertEqual(tokens[2].type, 'STRING')
        self.assertEqual(tokens[2].value, 'foo')

        tokens = self.lex("`foo'`foo'")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].type, 'STRING')
        self.assertEqual(tokens[0].value, 'foo')
        self.assertEqual(tokens[1].type, 'STRING')
        self.assertEqual(tokens[1].value, 'foo')

    def test_comments(self):
        tokens = self.lex("# foo")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, 'COMMENT')
        self.assertEqual(tokens[0].value, '# foo')

        tokens = self.lex("foo # foo")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, 'IDENTIFIER')
        self.assertEqual(tokens[0].value, 'foo')
        self.assertEqual(tokens[1], ' ')
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
        self.assertEqual(tokens[2], '\n')
        self.assertEqual(tokens[3].type, 'IDENTIFIER')
        self.assertEqual(tokens[3].value, 'foo')

class ParserTests(unittest.TestCase):
    pass

class ComparisonTests(unittest.TestCase):
    def check_file(self, input_file, expected_file, thing):
        expected = open(expected_file, 'r').read()
        if thing == 'm4':
            # check m4 output
            m4_output = subprocess.check_output(['m4', input_file])
            self.assertEqual(m4_output, expected)
        elif thing == 'parser':
            stream = StringIO()
            Parser(open(input_file, 'r').read()).parse(stream=stream)
            self.assertEqual(stream.getvalue(), expected)

def create_test(input_file, output_file, thing):
    def do_test(self):
        self.check_file(input_file, output_file, thing)
    return do_test

def setup_comparison_tests():
    test_dir = os.path.join(os.path.dirname(__file__), 'test')
    for input_file in glob.glob(os.path.join(test_dir, '*.in')):
        output_file = os.path.splitext(input_file)[0] + '.out'
        for thing in ('m4', 'parser'):
            test_method = create_test(input_file, output_file, thing)
            test_method.__name__ = 'test_file_%s_%s' % (os.path.splitext(os.path.basename(input_file))[0], thing)
            setattr(ComparisonTests, test_method.__name__, test_method)

if __name__ == '__main__':
    setup_comparison_tests()
    unittest.main()
