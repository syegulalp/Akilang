# Test all code generation functions.

import unittest
from core.error import AkiTypeErr, AkiSyntaxErr, AkiBaseErr, AkiOpError


class TestLexer(unittest.TestCase):
    from core.repl import Repl
    from core.akitypes import AkiTypeMgr

    mgr = AkiTypeMgr()
    types = mgr.types
    r = Repl(typemgr=mgr)
    i = r.interactive

    def _e(self, tests):
        for text, result in tests:
            for _ in self.i(text, True):
                pass
            self.assertEqual(_, result)

    def _ex(self, err_type, tests):
        for text, _ in tests:
            with self.assertRaises(err_type):
                for _ in self.i(text, True):
                    pass

    def test_constant(self):
        self._e(((r"2", 2), (r"2.0", 2.0), (r"0hff", -1), (r"0xff", 255)))

    def test_basic_ops(self):
        self._e(
            (
                (r"2+2", 4),
                (r"2-2", 0),
                (r"2*2", 4),
                (r"2*-2", -4),
                (r"4-5", -1),
                (r"8/4", 2),
                (r"(2+2)/2", 2),
                (r"(2+2)+(2*2)", 8),
                (r"2.0+3.0", 5),
                (r"2.0-3.0", -1),
                (r"2.0*3.0", 6),
                (r"6.0/3.0", 2),
            )
        )

    def test_andor_ops(self):
        self._e(
            (
                (r"2 and 3", 3),
                (r"3 and 3", 3),
                (r"2 and 0", 0),
                (r"0 and 2", 0),
                (r"0 and 0", 0),
                (r"2 or 3", 2),
                (r"3 or 3", 3),
                (r"2 or 0", 2),
                (r"0 or 2", 2),
                (r"0 or 0", 0),
            )
        )

    def test_neg_ops(self):
        self._e(
            ((r"-1", -1), (r"-1.0", -1.0), (r"-0", 0), (r"--1", 1), (r"--1.0", 1.0))
        )

    def test_not_ops(self):
        self._e(
            (
                (r"not 1", False),
                (r"not 0", True),
                (r"not 32", False),
                (r"not 0.0", True),
                (r"not 32.1", False),
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
                (r"True == True", 1),
                (r"True == False", 0),
                (r"True != False", 1),
                (r"False == False", 1),
                (r"False != False", 0),
            )
        )

        self._ex(AkiTypeErr, ((r"False == 0", 0), (r"True == 1", 0)))

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
                (r"var x=1, y=2 if x==2 or y==1 3 else 4", 4),
                (r"var x=1, y=2 if x==1 or y==2 3 else 4", 3),
                (r"var x=1, y=2 if x==1 and y==2 3 else 4", 3),
                (r"var x=1, y=2 if x==2 and y==1 3 else 4", 4),
            )
        )

    def test_expressionblock_syntax(self):
        self._e((("var x=1,y=2 x+y", 3),))

    def test_var_assignment(self):
        self._e(
            (
                # Default type
                (r"var x=1 x", 1),
                # Explicit type
                (r"var x:f64=2.2 x", 2.2),
                # Implicit type
                (r"var x=3.3 x", 3.3),
                (r"var x,y,z x=y=z=1", 1),
                (r"var x,y,z x=y=z=1 x", 1),
                (r"var x,y,z x=y=z=1 y", 1),
                (r"var x,y,z x=y=z=1 z", 1),
            )
        )

    def test_type_trapping(self):
        self._ex(
            AkiTypeErr,
            ((r"var x:f32=1", None), (r"var x:i32=1.0", None), (r"3+32.0", None)),
        )

    def test_function_defs(self):
        self._e(((r"def m0(){1} m0()", 1), (r"def m1(){1} def m2(){2} m1()+m2()", 3)))

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
                (r"def m2(y,z=1){y+z} m2(2)", 3),
                (r"def m3(y=2,z=1){y+z} m3()", 3),
            )
        )
        self.r.repl_cpl.codegen.typemgr.reset()
        self._ex(AkiSyntaxErr, ((r"def m1(z=1,y){z+y", None),))

    def test_func_arg_type_trapping(self):
        self._ex(
            AkiTypeErr,
            ((r"def m1(x:i32){x} m1(1.0)", None), (r"def m2(x:f32){x} m2(3)", None)),
        )

    def test_func_arg_count_trapping(self):
        self._ex(
            AkiSyntaxErr,
            (
                (r"def m1(x=1,y=2){x+y} m1(1,2,3)", None),
                (r"def m2(x,y,z){x+y} m2(1,2)", None),
                (r"def m3(){0} m3(1,2)", None),
            ),
        )

    def test_inline_type_declarations(self):
        self._e(((r"var x:i32=1 x==i32(1)", True),))

        self._ex(AkiTypeErr, ((r"var x:i32=1 x==i64(1)", None),))

    def test_type_comparison(self):
        self._e(
            (
                (r"var x=1,y=2 type(x)==type(y)", True),
                (r"i32==i32", True),
                (r"i32==i64", False),
                (r"var x=1,y=2 type(x)!=type(y)", False),
                (r"type(i32)", "<type:type>"),
                (r"i32", "<type:i32>"),
                (r"def x(){} type(x)", "<type:func():i32>"),
                (r"def y(z:i32){z} type(y)", "<type:func(:i32):i32>"),
                (r"def q(z:i64):i64{z} type(q)", "<type:func(:i64):i64>"),
            )
        )
        self._ex(AkiOpError, ((r"var x=1,y=2 type(x)<type(y)", None),))

    def test_pointer(self):
        self._e(((r"var x:ptr i32 x", "<ptr i32 @ 0x0>"),))

    def test_function_pointer(self):
        self._e(
            (
                (r"var x:func():i32 x", "<function:func():i32 @ 0x0>"),
                (r"var x:func(:i32):i32 x", "<function:func(:i32):i32 @ 0x0>"),
                (r"def g0(){32} var x=g0 x()", 32),
                (r"def g1(){32} def g2(x){32+x} var x=g1,y=g2 x()+y(1)", 65),
                (
                    r"def g3(){32} def g4(x){32+x} var x=g3 var y=x var z=g4 x()+y()+z(1)",
                    97,
                ),
            )
        )

    def test_string_constant(self):
        self._e(
            (
                (r'"hi"', '"hi"'),
                (r'{var x="hi" x}', '"hi"'),
                (r'{var x:str x="hi" x}', '"hi"'),
                (r"var x:str x", '""'),
                (r"if 1 'hi' else 'bye'", '"hi"'),
            )
        )

    # Trap expressions that return no value, like `var`
    
    def test_nonyielding_expression_trap(self):        
        self._ex(AkiSyntaxErr,(
            (r"if {var x:i32=1} 2 else 3", None),
            (r"{var x:i32=1}==1", None)
            
        )
    )

    def test_function_default_trap(self):
        self._ex(AkiSyntaxErr, (
            (r"def x1(x={var x:i32=1 x}){}", None),
        ))

    def test_ref_deref(self):
        self._e(
            (
                # This first test ensures the original `x` is not clobbered
                (r"var x=32 var y=ref(x) var z=deref(y) x", 32),
                (r"var x=32 var y=ref(x) var z=deref(y) z", 32),
                (
                    r"var x=32 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) z",
                    32,
                ),
                (
                    r"var x=32 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) x",
                    32,
                ),
                (r"def g1(){32} var y=ref(g1) var z=deref(y) z()", 32),
                (r"def g1(){32} var x=g1 var y=ref(x) var z=deref(y) z()", 32),
                (r"def g1(){32} var x=g1 var y=ref(x) var z=deref(y) x()", 32),
                (r"def g1(){32} var x=ref(g1) var y=deref(x) y()", 32),
                (
                    r"def g1(){32} var x=g1 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) z()",
                    32,
                ),
                (
                    r"def g1(){32} var x=g1 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) x()",
                    32,
                ),
                
                # TODO: doesn't work yet
                #(r'def b1(x:ptr i32){x} var q=ref(b1)',0)
            )
        )
        self._ex(
            AkiTypeErr,
            (
                # `y()` is a pointer, not a callable
                (
                    r"def g1(){32} var x=g1 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) y()",
                    None,
                ),
                # you can't `ref` or `deref` anything not a variable
                (r"ref(32)", None),
                (r"deref(32)", None),
                # `x` is not a reference
                (r"var x=1 deref(x)", None),
            ),
        )

    def test_cast(self):
        self._e(
            (
                # truncation
                (r'unsafe cast(0x000000ff,u8)',255),
                (r'type(unsafe cast(0x000000ff,u8))=={var x:u8 type(x)}',True),
                # zero extend
                (r'unsafe cast(0xff,u64)',255),
                (r'type(unsafe cast(0xff,u64))=={var x:u64 type(x)}',True),
                # signed to unsigned
                (r'unsafe cast(0hff,i8)',-1),
                (r'type(unsafe cast(0hff,i8))=={var x:i8 type(x)}',True),
                # int to ptr
                (r'var x:u_size var y=unsafe cast(x, ptr u_mem) type(y)', '<type:ptr u8>'),
                # ptr to int
                (r'var x:ptr u_mem var y=unsafe cast(x, u_size) type(y)', '<type:u64>')
            )
        )
    def test_incorrect_casting(self):
        self._ex(AkiTypeErr,
        (
            (r'var x:ptr u_mem var y=unsafe cast(x, i32) type(y)', None),
            (r'var x:i32 var y=unsafe cast(x, ptr u_mem) type(y)', None),
            (r'unsafe cast(32,str)', None),
            (r'unsafe cast("Hello",i32)', None),
        )
    )
    
    def test_unsafe_trapping(self):
        self._ex(AkiSyntaxErr,
            (
                # `cast` operations are unsafe
                (r'cast(2,f64)', None),
            )
        )

    def test_array(self):
        self._e(
            (
                (r'var x:array(:i32)[2,2] x[0,0]=32 x[0,1]=12 x[1,0]=8 x[0,1]+x[0,0]+x[1,0]',52),
            )

        )
    def test_array_trapping(self):
        self._ex(AkiTypeErr,
            (
                # arrays of non-scalars are not permitted
                (r'var x:array(:str)[20]', None),
                # assignments to non-array types not permitted
                (r'var x:array(:i32)[20]=0', None),
            )
        )

    def test_pointer_comparison(self):
        self._e(
            (
                (r'def a1(x:ptr i32){x} var x=32 var y=ref(x) var z=a1(y) z==y', True),
            )
        )


    def test_autoset_return_type(self):
        self._e(
            (
                (f'def a(){32} type(a())==i32',True),
                (f'def a(){32} type(a)==func():i32',True),
            )
        )