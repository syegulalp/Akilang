import unittest

from core import lex
from sly.lex import Token


class TestLexer(unittest.TestCase):
    l = lex._AkiLexer.tokenize

    def _render(self):
        """
        Used to render the confirmed output of the token list to our test case.
        """

        t = self._generate_tokens()

        print("[")
        for _ in t:
            print([getattr(_, x) for x in _.__slots__], ",")
        print("]")

    def _generate_tokens(self):
        t = self.l(
            "1+2.0 hello:i32 (_f16) {-32,64} s=t r==1 def x(a:i32) var s=1 2+1 3-2 4*3 5/4 var x=8.0//2 if not x y else z a:ptr i32"
        )

        t = [_ for _ in t]
        return t

    def test_tokens_and_values(self):
        t = self._generate_tokens()
        # self._render()

        slots = Token.__slots__

        tests = [
            ["INTEGER", 1, 1, 0],
            ["PLUS", "+", 1, 1],
            ["FLOAT", 2.0, 1, 2],
            ["NAME", "hello", 1, 6],
            ["COLON", ":", 1, 11],
            ["NAME", "i32", 1, 12],
            ["LPAREN", "(", 1, 16],
            ["NAME", "_f16", 1, 17],
            ["RPAREN", ")", 1, 21],
            ["LBRACE", "{", 1, 23],
            ["MINUS", "-", 1, 24],
            ["INTEGER", 32, 1, 25],
            ["COMMA", ",", 1, 27],
            ["INTEGER", 64, 1, 28],
            ["RBRACE", "}", 1, 30],
            ["NAME", "s", 1, 32],
            ["ASSIGN", "=", 1, 33],
            ["NAME", "t", 1, 34],
            ["NAME", "r", 1, 36],
            ["EQ", "==", 1, 37],
            ["INTEGER", 1, 1, 39],
            ["DEF", "def", 1, 41],
            ["NAME", "x", 1, 45],
            ["LPAREN", "(", 1, 46],
            ["NAME", "a", 1, 47],
            ["COLON", ":", 1, 48],
            ["NAME", "i32", 1, 49],
            ["RPAREN", ")", 1, 52],
            ["VAR", "var", 1, 54],
            ["NAME", "s", 1, 58],
            ["ASSIGN", "=", 1, 59],
            ["INTEGER", 1, 1, 60],
            ["INTEGER", 2, 1, 62],
            ["PLUS", "+", 1, 63],
            ["INTEGER", 1, 1, 64],
            ["INTEGER", 3, 1, 66],
            ["MINUS", "-", 1, 67],
            ["INTEGER", 2, 1, 68],
            ["INTEGER", 4, 1, 70],
            ["TIMES", "*", 1, 71],
            ["INTEGER", 3, 1, 72],
            ["INTEGER", 5, 1, 74],
            ["DIV", "/", 1, 75],
            ["INTEGER", 4, 1, 76],
            ["VAR", "var", 1, 78],
            ["NAME", "x", 1, 82],
            ["ASSIGN", "=", 1, 83],
            ["FLOAT", 8.0, 1, 84],
            ["INT_DIV", "//", 1, 87],
            ["INTEGER", 2, 1, 89],
            ["IF", "if", 1, 91],
            ["NOT", "not", 1, 94],
            ["NAME", "x", 1, 98],
            ["NAME", "y", 1, 100],
            ["ELSE", "else", 1, 102],
            ["NAME", "z", 1, 107],
            ["NAME", "a", 1, 109],
            ["COLON", ":", 1, 110],
            ["PTR", "ptr", 1, 111],
            ["NAME", "i32", 1, 115],
        ]

        for tok, test in zip(t, tests):
            for id, x in enumerate(slots):
                self.assertEqual(test[id], getattr(tok, slots[id]))
