from . import Parser

import sys

if __name__ == '__main__':
    Parser(sys.stdin.buffer.read()).parse()
