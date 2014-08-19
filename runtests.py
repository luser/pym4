#!/usr/bin/env python

import glob
import os
import subprocess
import unittest
from StringIO import StringIO

from m4 import Lexer, Parser

class LexerTests(unittest.TestCase):
    pass

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
