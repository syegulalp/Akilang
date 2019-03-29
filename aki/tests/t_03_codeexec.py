# Test all code generation functions.

import unittest
from core.error import AkiTypeErr


class TestLexer(unittest.TestCase):
    from core.repl import Repl

    r = Repl()
    i = r.interactive

    def _e(self, tests):
        for text, result in tests:
            for _ in self.i(text, True):
                pass
            self.assertEqual(_, result)

    def _ex(self, err_type, tests):
        with self.assertRaises(err_type):
            for text, result in tests:
                for _ in self.i(text, True):
                    pass

    def test_basic_ops(self):
        self._e(
            (
                ("2+2", 4),
                ("2-2", 0),
                ("2*2", 4),
                ("2*-2", -4),
                ("2.0+3.0", 5),
                ("4-5", -1),
                ("8/4", 2),
                ("(2+2)/2", 2),
                ("(2+2)+(2*2)", 8),
            )
        )

    def test_comparisons_int(self):
        self._e(
            (
                ("2>1", 1),
                ("2<1", 0),
                ("2>=1", 1),
                ("2<=1", 0),
                ("2!=1", 1),
                ("2==1", 0),
                ("2==2", 1),
            )
        )

    def test_comparisons_float(self):
        self._e(
            (
                ("2.0>1.0", 1),
                ("2.0<1.0", 0),
                ("2.0>=1.0", 1),
                ("2.0<=1.0", 0),
                ("2.0!=1.0", 1),
                ("2.0==1.0", 0),
                ("2.0==2.0", 1),
            )
        )

    def test_basic_control_flow(self):
        self._e(
            (
                ("if 1 2 else 3", 2),
                ("if 0 2 else 3", 3),
                ("when 1 2 else 3", 1),
                ("when 0 2 else 3", 0),
            )
        )

    def test_expressionblock_syntax(self):
        self._e((("{var x=1,y=2 x+y}", 3),))

    def test_var_assignment(self):
        self._e(
            (
                # Default type
                ("{var x=1 x}", 1),
                # Explicit type
                ("{var x:f32=2.2 x}", 2.200000047683716),
                # Implicit type
                ("{var x=3.3 x}", 3.299999952316284)
                # Note that we will deal with floating point
                # issues later
            )
        )

    def test_type_trapping(self):
        self._ex(AkiTypeErr,
            (
                ("var x:f32=1", None),
                ("var x:i32=1.0", None),
                ("3+32.0", None),
            )
        )

    def test_function_defs(self):
        self._e(((r"def m1(){1} m1()", 1), (r"def m1(){1} def m2(){2} m1()+m2()", 3)))

    def test_with(self):
        self._e(
            ((r"def m1(z){with var q:i32 loop (q=0, q<20, q+1) {z+=1} z} m1(0)", 20),)
        )

    def test_break(self):
        self._e(((r"def m1(z){var q=0 loop () {q+=1 when q==20 break} q} m1(0)", 20),))
