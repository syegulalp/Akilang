import unittest

from core.lexer import Position, Lexer, Token, TokenKind
from core.vartypes import VarTypes

class TestLexer(unittest.TestCase):

    maxDiff = None

    def _assert_toks(self, toks, kinds):
        """Assert that the list of toks has the given kinds."""
        self.assertEqual([t.kind.name for t in toks], kinds)

    def test_lexer_simple_tokens_and_values(self):
        l = Lexer('a+1.')
        toks = list(l.tokens())

        pos = Position(l.buf, 1, 0)
        self.assertEqual(toks[0], Token(TokenKind.IDENTIFIER, 'a', None, pos))

        pos = Position(l.buf, 1, 1)
        self.assertEqual(toks[1], Token(TokenKind.OPERATOR, '+', None, pos))

        pos = Position(l.buf, 1, 2)
        self.assertEqual(toks[2],
                         Token(TokenKind.NUMBER, '1.', VarTypes.f64, pos))

        pos = Position(l.buf, 1, 3)
        self.assertEqual(toks[3], Token(TokenKind.EOF, '', None, pos))

        pos = Position(l.buf, 1, 0)
        l = Lexer('0.1519')
        toks = list(l.tokens())
        self.assertEqual(toks[0],
                         Token(TokenKind.NUMBER, '0.1519', VarTypes.f64,
                               pos))

    def test_token_kinds(self):
        l = Lexer('10.1 def der extern foo var (')
        self._assert_toks(
            list(l.tokens()), [
                'NUMBER', 'DEF', 'IDENTIFIER', 'EXTERN', 'IDENTIFIER', 'VAR',
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

        pos = Position(l.buf, 1, 0)
        self.assertEqual(toks[0],
                         Token(TokenKind.NUMBER, '10.', VarTypes.f64, pos))
        pos = Position(l.buf, 1, 4)
        self.assertEqual(toks[1],
                         Token(TokenKind.NUMBER, '10', VarTypes.i32, pos))

        pos = Position(l.buf, 1, 7)
        self.assertEqual(toks[2],
                         Token(TokenKind.NUMBER, '10.0', VarTypes.f64, pos))

        pos = Position(l.buf, 1, 12)
        self.assertEqual(toks[3],
                         Token(TokenKind.NUMBER, '1', VarTypes.bool, pos))

        pos = Position(l.buf, 1, 15)
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