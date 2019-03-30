# Test all code generation functions.

import unittest
from core.error import AkiTypeErr, AkiSyntaxErr


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
                (r"2+2", 4),
                (r"2-2", 0),
                (r"2*2", 4),
                (r"2*-2", -4),
                (r"2.0+3.0", 5),
                (r"4-5", -1),
                (r"8/4", 2),
                (r"(2+2)/2", 2),
                (r"(2+2)+(2*2)", 8),
            )
        )

    def test_comparisons_int(self):
        self._e(
            (
                (r"2>1", 1),
                (r"2<1", 0),
                (r"2>=1", 1),
                (r"2<=1", 0),
                (r"2!=1", 1),
                (r"2==1", 0),
                (r"2==2", 1),
            )
        )

    def test_comparisons_float(self):
        self._e(
            (
                (r"2.0>1.0", 1),
                (r"2.0<1.0", 0),
                (r"2.0>=1.0", 1),
                (r"2.0<=1.0", 0),
                (r"2.0!=1.0", 1),
                (r"2.0==1.0", 0),
                (r"2.0==2.0", 1),
            )
        )

    def test_basic_control_flow(self):
        self._e(
            (
                (r"if 1 2 else 3", 2),
                (r"if 0 2 else 3", 3),
                (r"when 1 2 else 3", 1),
                (r"when 0 2 else 3", 0),
            )
        )

    def test_expressionblock_syntax(self):
        self._e((("{var x=1,y=2 x+y}", 3),))

    def test_var_assignment(self):
        self._e(
            (
                # Default type
                (r"{var x=1 x}", 1),
                # Explicit type
                (r"{var x:f32=2.2 x}", 2.200000047683716),
                # Implicit type
                (r"{var x=3.3 x}", 3.299999952316284)
                # Note that we will deal with floating point
                # issues later
            )
        )

    def test_type_trapping(self):
        self._ex(AkiTypeErr,
            (
                (r"var x:f32=1", None),
                (r"var x:i32=1.0", None),
                (r"3+32.0", None),
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
    
    def test_default_function_arguments(self):
        self._e(
            (
                (r"def m1(z=1){z} m1()",1),
                (r"def m1(y,z=1){y+z} m1(2)",3),
                (r"def m1(y=2,z=1){y+z} m1()",3),
            )
        )
        self._ex(AkiSyntaxErr,
            (
                (r"def m1(z=1,y){z+y}", None),
            )
        )