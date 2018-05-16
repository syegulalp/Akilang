from enum import Enum, unique
from collections import namedtuple
import llvmlite.ir as ir
from vartypes import VarTypes
from errors import AkiSyntaxError
from operators import BUILTIN_OP, BUILTIN_UNARY_OP

from functools import lru_cache

# Each token is a tuple of kind and value. kind is one of the enumeration values
# in TokenKind. value is the textual value of the token in the input.


@unique
class TokenKind(Enum):
    EOF = -1
    IDENTIFIER = -4
    NUMBER = -5
    STRING = -6
    PUNCTUATOR = -7
    OPERATOR = -10

    VARTYPE = -50

    # Keywords are less than -100

    DEF = -1010
    EXTERN = -1020
    CONST = -1030
    UNI = -1040
    CLASS = -1041

    PTR = -1045

    RETURN = -1047
    BREAK = -1048
    VAR = -1050
    LET = -1060
    WITH = -1110
    LOOP = -1115
    IF = -1200
    WHEN = -1250
    THEN = -1300
    ELSE = -1400
    ELIF = -1401
    FOR = -1500
    IN = -1600
    WHILE = -1650
    MATCH = -1660
    DEFAULT = -1665

    BINARY = -1700
    UNARY = -1800


ESCAPES = {'n': 10, 'r': 13, "'": ord("'"), '"': ord('"')}

PUNCTUATORS = '()[]{},:'
COMMENT = "#"

Token = namedtuple('Token', 'kind value vartype position')


class Position():
    def __init__(self, buffer, line=1, col=0, absposition=0, lineposition=0):
        self.line = line
        self.col = col
        self.absposition = absposition
        self.lineposition = lineposition
        self.buffer = buffer

    def advance(self, newline=False):
        if newline:
            self.line += 1
            self.col = 0
            self.absposition += 1
            self.lineposition = self.absposition
        else:
            self.col += 1
            self.absposition += 1

    @property
    def copy(self):
        return Position(self.buffer, self.line, self.col, self.absposition,
                        self.lineposition)

    def __repr__(self):
        return f'line {self.line}:{self.col}'

    def __eq__(self, other):
        return self.line == other.line and self.col == other.col


@lru_cache()
def get_keyword(name):
    try:
        kind = TokenKind[name.upper()]
        if kind.value < -100 and kind._name_.lower() == name:
            return kind
    except KeyError:
        pass
    return None


class Lexer(object):
    """Lexer for Akilang.
    Initialize the lexer with a string buffer. tokens() returns a generator that
    can be queried for tokens. The generator will emit an EOF token before
    stopping.
    """

    def __init__(self, buf):
        assert len(buf) >= 1
        self.buf = buf
        self.pos = 0
        self.lastchar = self.buf[0]
        self.position = Position(buf)

    def _advance(self):
        try:
            self.pos += 1
            self.lastchar = self.buf[self.pos]
            self.position.advance(self.lastchar == '\n')

        except IndexError:
            self.lastchar = ''

    def tokens(self):

        pos = self.position.copy

        while self.lastchar:

            vartype = None

            #pos = self.position.copy

            # Skip whitespace
            while self.lastchar.isspace():
                self._advance()

            pos = self.position.copy
            
            if not self.lastchar:
                break

            # String
            if self.lastchar in ('"\''):
                opening_quote = self.lastchar
                str = []
                self._advance()
                while self.lastchar and self.lastchar != opening_quote:
                    # Process escape codes
                    if self.lastchar in ('\\', ):
                        self._advance()
                        if self.lastchar in ESCAPES:
                            str.append(chr(ESCAPES[self.lastchar]))
                        elif self.lastchar in 'x':
                            hex = []
                            for _ in range(0, 2):
                                self._advance()
                                hex.append(self.lastchar)
                            try:
                                str.append(chr(int(''.join(hex), 16)))
                            except ValueError:
                                raise AkiSyntaxError(
                                    f'invalid hex value "{"".join(hex)}"',
                                    self.position)
                        else:
                            raise AkiSyntaxError(
                                f'escape code "\\{self.lastchar}" not recognized',
                                self.position)
                    else:
                        str.append(self.lastchar)
                    self._advance()
                str = ''.join(str)
                self._advance()
                yield Token(TokenKind.STRING, str, VarTypes.str, pos)

            # Identifier or keyword, including vartypes
            elif self.lastchar.isalpha() or self.lastchar in ('_', ):
                id_str = []
                while self.lastchar.isalnum() or self.lastchar in ('_', ):
                    id_str.append(self.lastchar)
                    self._advance()
                id_str = ''.join(id_str)

                if id_str in BUILTIN_OP:
                    yield Token(TokenKind.OPERATOR, id_str, None, pos)
                elif id_str in BUILTIN_UNARY_OP:
                    yield Token(TokenKind.OPERATOR, id_str, None, pos)
                elif get_keyword(id_str):
                    yield Token(get_keyword(id_str), id_str, None, pos)
                elif id_str in VarTypes:
                    yield Token(TokenKind.VARTYPE, id_str, None, pos)
                else:
                    yield Token(TokenKind.IDENTIFIER, id_str, vartype, pos)

            # we should attempt to match these against our list of operators

            # Number
            elif self.lastchar.isdigit(): # or self.lastchar == '.':
                num_str = []
                while self.lastchar and (self.lastchar.isdigit()
                                         or self.lastchar in '.bBiIUu'):
                    num_str.append(self.lastchar)
                    self._advance()
                num = ''.join(num_str)

                if '.' in num:
                    if num[:-1].isalpha():
                        raise AkiSyntaxError(
                            f'Invalid floating-point literal format "{num}"',
                            pos)
                    vartype = VarTypes.f64

                elif num[-1] == 'B':
                    vartype = VarTypes.byte
                    num = num[0:-1 - (num[-2] == '.')]

                elif num[-1] == 'b':
                    vartype = VarTypes.bool
                    num = num[0:-1]

                elif num[-1] == 'I':
                    vartype = VarTypes.i64
                    num = num[0:-1]

                elif num[-1] == 'i':
                    vartype = VarTypes.i32
                    num = num[0:-1]

                elif num[-1] == 'U':
                    vartype = VarTypes.u64
                    num = num[0:-1]

                elif num[-1] == 'u':
                    vartype = VarTypes.u32
                    num = num[0:-1]

                else:
                    vartype = VarTypes.i32

                yield Token(TokenKind.NUMBER, num, vartype, pos)

            # Comment
            elif self.lastchar == COMMENT:
                self._advance()
                while self.lastchar and self.lastchar not in '\r\n':
                    self._advance()
            elif self.lastchar in PUNCTUATORS:
                yield Token(TokenKind.PUNCTUATOR, self.lastchar, None, pos)
                self._advance()

            #finally, we attempt to match operators that don't have the same
            #naming convention as user symbols

            elif self.lastchar:
                op = []
                while True:
                    op.append(self.lastchar)
                    self._advance()
                    if ''.join(op) + self.lastchar not in BUILTIN_OP:
                        break
                yield Token(TokenKind.OPERATOR, ''.join(op), None, pos)

        yield Token(TokenKind.EOF, '', None, self.position.copy)


#---- Some unit tests ----#

import unittest


class TestLexer(unittest.TestCase):

    maxDiff = None

    def _assert_toks(self, toks, kinds):
        """Assert that the list of toks has the given kinds."""
        self.assertEqual([t.kind.name for t in toks], kinds)

    def test_lexer_simple_tokens_and_values(self):
        l = Lexer('a+1.')
        toks = list(l.tokens())

        pos = Position(l.buf, 1, 1)
        self.assertEqual(toks[0], Token(TokenKind.IDENTIFIER, 'a', None, pos))

        pos = Position(l.buf, 1, 2)
        self.assertEqual(toks[1], Token(TokenKind.OPERATOR, '+', None, pos))

        pos = Position(l.buf, 1, 3)
        self.assertEqual(toks[2],
                         Token(TokenKind.NUMBER, '1.', VarTypes.f64, pos))

        pos = Position(l.buf, 1, 4)
        self.assertEqual(toks[3], Token(TokenKind.EOF, '', None, pos))

        pos = Position(l.buf, 1, 1)
        l = Lexer('0.1519')
        toks = list(l.tokens())
        self.assertEqual(toks[0],
                         Token(TokenKind.NUMBER, '0.1519', VarTypes.f64,
                               pos))

    def test_token_kinds(self):
        l = Lexer('10.1 def der extern foo let (')
        self._assert_toks(
            list(l.tokens()), [
                'NUMBER', 'DEF', 'IDENTIFIER', 'EXTERN', 'IDENTIFIER', 'LET',
                'PUNCTUATOR', 'EOF'
            ])

        l = Lexer('+- 1 2 22 22.4 a b2 C3d')
        self._assert_toks(
            list(l.tokens()), [
                'OPERATOR', 'OPERATOR', 'NUMBER', 'NUMBER', 'NUMBER', 'NUMBER',
                'IDENTIFIER', 'IDENTIFIER', 'IDENTIFIER', 'EOF'
            ])

    def test_var_assignments(self):
        l = Lexer('10. 10 10.0 1b 10B')
        toks = list(l.tokens())

        pos = Position(l.buf, 1, 1)
        self.assertEqual(toks[0],
                         Token(TokenKind.NUMBER, '10.', VarTypes.f64, pos))
        pos = Position(l.buf, 1, 5)
        self.assertEqual(toks[1],
                         Token(TokenKind.NUMBER, '10', VarTypes.i32, pos))

        pos = Position(l.buf, 1, 8)
        self.assertEqual(toks[2],
                         Token(TokenKind.NUMBER, '10.0', VarTypes.f64, pos))

        pos = Position(l.buf, 1, 13)
        self.assertEqual(toks[3],
                         Token(TokenKind.NUMBER, '1', VarTypes.bool, pos))

        pos = Position(l.buf, 1, 16)
        self.assertEqual(toks[4],
                         Token(TokenKind.NUMBER, '10', VarTypes.i8, pos))

    def test_string_assignment(self):
        l = Lexer('"Hello world"')
        toks = list(l.tokens())
        pos = Position(1, 1)
        self.assertEqual(toks[0],
                         Token(TokenKind.STRING, 'Hello world', VarTypes.str,
                               pos))

    def test_skip_whitespace_comments(self):
        l = Lexer('''
            def foo # this is a comment
            # another comment
            \t\t\t10
            ''')
        self._assert_toks(
            list(l.tokens()), ['DEF', 'IDENTIFIER', 'NUMBER', 'EOF'])


#---- Typical example use ----#

if __name__ == '__main__':

    import sys
    program = 'uni (x=1, f:int32 int32 y=1, z=u"Hello world", i8[1,1] q=[1]) def ptr int32 bina(a b) a + b >= 1 convert(32,u64) ?? == != <= if a and b < 0. then not a else a [1,2,3,4]'
    if len(sys.argv) > 1:
        program = ' '.join(sys.argv[1:])
    print("\nPROGRAM: ", program)
    print("\nTOKENS: ")
    lexer = Lexer(program)
    for token in lexer.tokens():
        print("  ", token.kind.name, token.value)
