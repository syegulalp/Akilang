from core.vartypes import generate_vartypes
from core.errors import AkiSyntaxError
from core.operators import BUILTIN_OP, BUILTIN_UNARY_OP
from functools import lru_cache

import llvmlite.ir as ir

# Each token is a tuple of kind and value. kind is one of the enumeration values
# in TokenKind. value is the textual value of the token in the input.

from core.tokens import Token, TokenKind, ESCAPES, COMMENT, PUNCTUATORS


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

    def __init__(self, buf, vartypes=generate_vartypes()):
        assert len(buf) >= 1
        self.buf = buf
        self.pos = 0
        self.lastchar = self.buf[0]
        self.position = Position(buf)
        self.vartypes = vartypes

    def _advance(self):
        try:
            self.prevchar = self.buf[self.pos]
            self.pos += 1
            self.lastchar = self.buf[self.pos]
            self.position.advance(self.prevchar in '\r\n')

        except IndexError:
            self.lastchar = ''

    def tokens(self):

        VarTypes = self.vartypes

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
                opening_quote_position = self.position.copy
                new_str = []
                self._advance()
                while self.lastchar and self.lastchar != opening_quote:
                    # Process escape codes
                    if self.lastchar in ('\\',):
                        self._advance()
                        if self.lastchar in ESCAPES:
                            # new_str.append(chr(ESCAPES[self.lastchar]))
                            new_str.append((ESCAPES[self.lastchar]))
                        elif self.lastchar in 'x':
                            hex = []
                            for _ in range(0, 2):
                                self._advance()
                                hex.append(self.lastchar)
                            try:
                                new_str.append(chr(int(''.join(hex), 16)))
                            except ValueError:
                                raise AkiSyntaxError(
                                    f'invalid hex value "{"".join(hex)}"',
                                    self.position)
                        else:
                            raise AkiSyntaxError(
                                f'escape code "\\{self.lastchar}" not recognized',
                                self.position)
                    else:
                        new_str.append(self.lastchar)
                    self._advance()
                    if not self.lastchar:
                        raise AkiSyntaxError(
                            f'unclosed quote (missing {opening_quote})',
                            opening_quote_position
                        )
                new_str = ''.join(new_str)
                self._advance()
                yield Token(TokenKind.STRING, new_str, VarTypes.str, pos)

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

            # Number
            elif self.lastchar.isdigit():
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

            # finally, we attempt to match operators that don't have the same
            # naming convention as user symbols

            elif self.lastchar:
                op = []
                while self.lastchar:
                    op.append(self.lastchar)
                    self._advance()
                    if ''.join(op) + self.lastchar not in BUILTIN_OP:
                        break
                yield Token(TokenKind.OPERATOR, ''.join(op), None, pos)

        yield Token(TokenKind.EOF, '', None, self.position.copy)


#---- Typical example use ----#

# if __name__ == '__main__':
#     import sys
#     program = 'uni (x=1, f:int32 int32 y=1, z=u"Hello world", i8[1,1] q=[1]) def ptr int32 bina(a b) a + b >= 1 convert(32,u64) ?? == != <= if a and b < 0. then not a else a [1,2,3,4]'
#     if len(sys.argv) > 1:
#         program = ' '.join(sys.argv[1:])
#     print("\nPROGRAM: ", program)
#     print("\nTOKENS: ")
#     lexer = Lexer(program)
#     for token in lexer.tokens():
#         print("  ", token.kind.name, token.value)
