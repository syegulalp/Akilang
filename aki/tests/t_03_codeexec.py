# Test all code generation functions.

import unittest
from core.error import AkiTypeErr, AkiSyntaxErr, AkiBaseErr, AkiOpError
from core.akitypes import AkiTypes

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
        self._ex(
            AkiTypeErr,
            ((r"var x:f32=1", None), (r"var x:i32=1.0", None), (r"3+32.0", None)),
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
                (r"def m1(z=1){z} m1()", 1),
                (r"def m1(y,z=1){y+z} m1(2)", 3),
                (r"def m1(y=2,z=1){y+z} m1()", 3),
            )
        )
        self._ex(AkiSyntaxErr, ((r"def m1(z=1,y){z+y}", None),))

    def test_func_arg_type_trapping(self):
        self._ex(
            AkiTypeErr,
            ((r"def m1(x:i32){x} m1(1.0)", None), (r"def m1(x:f32){x} m1(3)", None)),
        )

    def test_func_arg_count_trapping(self):
        self._ex(
            AkiSyntaxErr,
            (
                (r"def m1(x=1,y=2){x+y} m1(1,2,3)", None),
                (r"def m1(x,y,z){x+y} m1(1,2)", None),
                (r"def m1(){0} m1(1,2)", None),
            ),
        )

    def test_inline_type_declarations(self):
        self._e(
            (
                (r"{var x:i32=1 x==i32(1)}", True),
            )
        )
        
        self._ex(
            AkiTypeErr,
            (
                (r"{var x:i32=1 x==i64(1)}", None),
            )
        )

    def test_type_comparison(self):
        self._e(
            (
                (r"{var x=1,y=2 type(x)==type(y)}", True),
                (r"i32==i32", True),
                (r"i32==i64", False),
                (r"{var x=1,y=2 type(x)!=type(y)}", False),
                (r'type(i32)', AkiTypes.type.enum_id),
                (r'i32', AkiTypes.i32.enum_id),
            )
        )
        self._ex(
            AkiOpError,
            (
                (r"{var x=1,y=2 type(x)<type(y)}", None),
            )
        )

    def test_pointer(self):
        self._e(
            (
                (r'{var x:ptr i32 x}', 0),
            )
        )
   
   
    def test_function_pointer(self):
        self._e(
            (
                (r'{var x:func():i32 x}', 0),
                (r'{var x:func(:i32):i32 x}', 0),
                (r'def g1(){32} {var x=g1 x()}',32),
                (r'def g1(){32} def g2(x){32+x} {var x=g1,y=g2 x()+y(1)}',65),
                (r'def g1(){32} def g2(x){32+x} {var x=g1 var y=x var z=g2 x()+y()+z(1)}',97)
            )
        )
