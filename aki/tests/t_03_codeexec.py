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

    def e(self, test, result):
        _ = [_ for _ in self.i(test, True)][0]
        self.assertEqual(_, result)

    def ex(self, err_type, test):
        with self.assertRaises(err_type):
            [_ for _ in self.i(test, True)]

    def test_constants(self):
        self.e(r"2", 2)
        self.e(r"2.0", 2.0)
        self.e(r"0hff", -1)
        self.e(r"0xff", 255)
        self.e(r"type(0x00:u64)", "<type:u64>")

    def test_math_integer(self):
        self.e(r"2+2", 4)
        self.e(r"2-2", 0)
        self.e(r"4-5", -1)
        self.e(r"2*2", 4)
        self.e(r"2*-2", -4)
        self.e(r"8/4", 2)

    def test_math_float(self):
        self.e(r"2.0+3.0", 5)
        self.e(r"2.0-3.0", -1)
        self.e(r"2.0*3.0", 6)
        self.e(r"6.0/3.0", 2)

    def test_nested_math(self):
        self.e(r"(2+2)/2", 2)
        self.e(r"(2+2)+(2*2)", 8)
        self.e(r"(2.0+2.5)/2.0", 2.25)
        self.e(r"(2.0+2.5)+(2.0*2.0)", 8.5)

    def test_andor_ops(self):
        self.e(r"2 and 3", 3)
        self.e(r"3 and 3", 3)
        self.e(r"2 and 0", 0)
        self.e(r"0 and 2", 0)
        self.e(r"0 and 0", 0)
        self.e(r"2 or 3", 2)
        self.e(r"3 or 3", 3)
        self.e(r"2 or 0", 2)
        self.e(r"0 or 2", 2)
        self.e(r"0 or 0", 0)

    def test_neg_ops(self):
        self.e(r"-1", -1)
        self.e(r"-1.0", -1.0),
        self.e(r"-0", 0)
        self.e(r"--1", 1)
        self.e(r"--1.0", 1.0)

    def test_not_ops(self):
        self.e(r"not 1", False)
        self.e(r"not 0", True)
        self.e(r"not 32", False)
        self.e(r"not 0.0", True)
        self.e(r"not 32.1", False)

    def test_comparisons_int(self):
        self.e(r"2>1", 1)
        self.e(r"2<1", 0)
        self.e(r"2>=1", 1)
        self.e(r"2<=1", 0)
        self.e(r"2!=1", 1)
        self.e(r"2==1", 0)
        self.e(r"2==2", 1)
        self.e(r"True == True", 1)
        self.e(r"True == False", 0)
        self.e(r"True != False", 1)
        self.e(r"False == False", 1)
        self.e(r"False != False", 0)

        self.ex(AkiTypeErr, r"False == 0")
        self.ex(AkiTypeErr, r"True == 1")

    def test_comparisons_float(self):
        self.e(r"2.0>1.0", 1)
        self.e(r"2.0<1.0", 0)
        self.e(r"2.0>=1.0", 1)
        self.e(r"2.0<=1.0", 0)
        self.e(r"2.0!=1.0", 1)
        self.e(r"2.0==1.0", 0)
        self.e(r"2.0==2.0", 1)

        self.ex(AkiTypeErr, r"False == 2.0")
        self.ex(AkiTypeErr, r"True == 0.0")

    def test_basic_control_flow(self):
        self.e(r"if 1 2 else 3", 2)
        self.e(r"if 0 2 else 3", 3)
        self.e(r"when 1 2 else 3", 1)
        self.e(r"when 0 2 else 3", 0)
        self.e(r"var x=1, y=2 if x==2 or y==1 3 else 4", 4)
        self.e(r"var x=1, y=2 if x==1 or y==2 3 else 4", 3)
        self.e(r"var x=1, y=2 if x==1 and y==2 3 else 4", 3)
        self.e(r"var x=1, y=2 if x==2 and y==1 3 else 4", 4)

    def test_expressionblock_syntax(self):
        self.e(r"var x=1,y=2 x+y", 3)

    def test_var_assignment(self):
        # Default type
        self.e(r"var x=1 x", 1)
        # Explicit type
        self.e(r"var x:f64=2.2 x", 2.2)
        # Implicit type
        self.e(r"var x=3.3 x", 3.3)
        self.e(r"var x,y,z x=y=z=1", 1)
        self.e(r"var x,y,z x=y=z=1 x", 1)
        self.e(r"var x,y,z x=y=z=1 y", 1)
        self.e(r"var x,y,z x=y=z=1 z", 1)

    def test_type_trapping(self):
        self.ex(AkiTypeErr, r"var x:f32=1")
        self.ex(AkiTypeErr, r"var x:i32=1.0")
        self.ex(AkiTypeErr, r"3+32.0")
        self.ex(AkiTypeErr, r"3.0+32")

    def test_function_defs(self):
        self.e(r"def m0(){1} m0()", 1)
        self.e(r"def m1(){1} def m2(){2} m1()+m2()", 3)

    def test_with(self):
        self.e(r"def m1(z){with var q:i32 loop (q=0, q<20, q+1) {z+=1} z} m1(0)", 20)

    def test_break(self):
        self.e(r"def m1(z){var q=0 loop () {q+=1 when q==20 break} q} m1(0)", 20)

    def test_default_function_arguments(self):
        self.e(r"def m1(z=1){z} m1()", 1)
        self.e(r"def m2(y,z=1){y+z} m2(2)", 3)
        self.e(r"def m3(y=2,z=1){y+z} m3()", 3)

        self.ex(AkiSyntaxErr, r"def m1(z=1,y){z+y")

    def test_func_arg_type_trapping(self):
        self.ex(AkiTypeErr, r"def m1(x:i32){x} m1(1.0)")
        self.ex(AkiTypeErr, r"def m2(x:f32){x} m2(3)")

    def test_func_arg_count_trapping(self):
        self.ex(AkiSyntaxErr, r"def m1(x=1,y=2){x+y} m1(1,2,3)")
        self.ex(AkiSyntaxErr, r"def m2(x,y,z){x+y} m2(1,2)")
        self.ex(AkiSyntaxErr, r"def m3(){0} m3(1,2)")

    def test_inline_type_declarations(self):
        self.e(r"var x:i32=1 x==1:i32", True)

        self.ex(AkiTypeErr, r"var x:i32=1 x==1:i64")

    def test_type_comparison(self):
        self.e(r"var x=1,y=2 type(x)==type(y)", True)
        self.e(r"i32==i32", True)
        self.e(r"i32==i64", False)
        self.e(r"var x=1,y=2 type(x)!=type(y)", False)
        self.e(r"type(i32)", "<type:type>")
        self.e(r"i32", "<type:i32>")
        self.e(r"def x(){} type(x)", "<type:func():i32>")
        self.e(r"def y(z:i32){z} type(y)", "<type:func(i32):i32>")
        self.e(r"def q(z:i64):i64{z} type(q)", "<type:func(i64):i64>")

        self.ex(AkiOpError, r"var x=1,y=2 type(x)<type(y)")

    def test_pointer(self):
        self.e(r"var x:ptr i32 x", "<ptr i32 @ 0x0>")

    def test_function_pointer(self):
        self.e(r"var x:func():i32 x", "<function:func():i32 @ 0x0>")
        self.e(r"var x:func(i32):i32 x", "<function:func(i32):i32 @ 0x0>")
        self.e(r"var x:func(i32, i64):i32 x", "<function:func(i32,i64):i32 @ 0x0>")
        self.e(r"def g0(){32} var x=g0 x()", 32)
        self.e(r"def g1(){32} def g2(x){32+x} var x=g1,y=g2 x()+y(1)", 65)
        self.e(
            r"def g3(){32} def g4(x){32+x} var x=g3 var y=x var z=g4 x()+y()+z(1)", 97
        )

    def test_string_constant(self):
        self.e(r'"hi"', '"hi"')
        self.e(r'{var x="hi" x}', '"hi"')
        self.e(r'{var x:str x="hi" x}', '"hi"')
        self.e(r"var x:str x", '""')
        self.e(r"if 1 'hi' else 'bye'", '"hi"')

    # Trap expressions that return no value, like `var`

    def test_nonyielding_expression_trap(self):
        self.ex(AkiSyntaxErr, r"if {var x:i32=1} 2 else 3")
        self.ex(AkiSyntaxErr, r"{var x:i32=1}==1")

    def test_function_default_trap(self):
        self.ex(AkiSyntaxErr, r"def x1(x={var x:i32=1 x}){}")

    def test_ref_deref(self):
        # This first test ensures the original `x` is not clobbered
        self.e(r"var x=32 var y=ref(x) var z=deref(y) x", 32)
        self.e(r"var x=32 var y=ref(x) var z=deref(y) z", 32)
        self.e(
            r"var x=32 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) z", 32
        )
        self.e(
            r"var x=32 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) x", 32
        )
        self.e(r"def g1(){32} var y=ref(g1) var z=deref(y) z()", 32)
        self.e(r"def g1(){32} var x=g1 var y=ref(x) var z=deref(y) z()", 32)
        self.e(r"def g1(){32} var x=g1 var y=ref(x) var z=deref(y) x()", 32)
        self.e(r"def g1(){32} var x=ref(g1) var y=deref(x) y()", 32)
        self.e(
            r"def g1(){32} var x=g1 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) z()",
            32,
        )
        self.e(
            r"def g1(){32} var x=g1 var y=ref(x) var q=ref(y) var t=deref(q) var z=deref(t) x()",
            32,
        )
        self.e(r"def b1(x:ptr i32){x} var q=ref(b1)", 0)
        self.e(r"var x:array i32[10] x[1]=10 var y=ref(x[1]) deref(y)", 10)

        # `y()` is a pointer, not a callable
        self.ex(AkiTypeErr, r"def g1(){32} var x=g1 var y=ref(x) var z=deref(y) y()")
        # you can't `ref` or `deref` anything not a variable
        self.ex(AkiTypeErr, r"ref(32)")
        self.ex(AkiTypeErr, r"deref(32)")
        # `x` is not a reference
        self.ex(AkiTypeErr, r"var x=1 deref(x)")

    def test_cast(self):
        # truncation
        self.e(r"unsafe cast(0x000000ff,u8)", 255)
        self.e(r"type(unsafe cast(0x000000ff,u8))=={var x:u8 type(x)}", True)
        # zero extend
        self.e(r"unsafe cast(0xff,u64)", 255)
        self.e(r"type(unsafe cast(0xff,u64))=={var x:u64 type(x)}", True)
        # signed to unsigned
        self.e(r"unsafe cast(0hff,i8)", -1)
        self.e(r"type(unsafe cast(0hff,i8))=={var x:i8 type(x)}", True)
        # int to ptr
        self.e(r"var x:u_size var y=unsafe cast(x, ptr u_mem) type(y)", "<type:ptr u8>")
        # ptr to int
        self.e(r"var x:ptr u_mem var y=unsafe cast(x, u_size) type(y)", "<type:u64>")

    def test_incorrect_casting(self):
        self.ex(AkiTypeErr, r"var x:ptr u_mem var y=unsafe cast(x, i32) type(y)")
        self.ex(AkiTypeErr, r"var x:i32 var y=unsafe cast(x, ptr u_mem) type(y)")
        self.ex(AkiTypeErr, r"unsafe cast(32,str)")
        self.ex(AkiTypeErr, r'unsafe cast("Hello",i32)')

    def test_unsafe_trapping(self):
        # `cast` operations are unsafe
        self.ex(AkiSyntaxErr, r"cast(2,f64)")

    def test_array(self):
        self.e(
            r"var x:array i32[2,2] x[0,0]=32 x[0,1]=12 x[1,0]=8 x[0,1]+x[0,0]+x[1,0]",
            52,
        )
        self.e(r"var x:array str[20] x[1]='Hi' x[1]", '"Hi"')
        self.e(
            r"def a(){30} def b(){64} var x:array func():i32[2,2] x[1,2]=a x[2,1]=b var c=x[1,2] var d=x[2,1] d()-c()",
            34,
        )

        # NOT FUNCTIONAL YET. We don't have a repr for arrays

        # self.e(r"var x: array i32[20] x", None)

        # We also don't yet have a direct array assignment mechanism

        # self.e(r"var x: array i32[2]=[8,16] x", None)

    def test_array_trapping(self):
        self.ex(AkiTypeErr, r"var x:array i32[20]=0")
        self.ex(AkiTypeErr, r"var x:array i32[20]=0")

    def test_pointer_comparison(self):
        self.e(r"def a1(x:ptr i32){x} var x=32 var y=ref(x) var z=a1(y) z==y", True)

    def test_autoset_return_type(self):
        self.e(r"def a(){32} type(a())==i32", True)
        self.e(r"def a(){32} type(a)==func():i32", True)

    def test_c_size(self):
        self.e(r"c_size('Hello there')", 12)
        self.e(r"c_size(1)", 4)
        self.e(r"c_size(1:u64)", 8)

    def test_size(self):
        self.e(r"size('Hello there')", 8)
        self.e(r"size(1)", 4)
        self.e(r"size(1:u64)", 8)

    def test_while(self):
        self.e(r"var x=1,q=20 while x<20 {x+=1} q+x", 40)
        self.e(r"var x=1 while x<20 {x+=1 if x==10 break} x", 10)

    def test_const(self):
        self.e(r"const {x=1} x", 1)
        self.e(r"const {x='hi'} x", '"hi"')
        self.ex(AkiTypeErr, r"const {x=1} x=2")

    def test_decorator(self):
        self.e(r"@noinline def m1(){32} m1()", 32)
        self.e(r"@inline def m1(){32} m1()", 32)
        self.ex(AkiSyntaxErr, r"@bogus def m1(){32} m1()")

    def test_return(self):
        self.e(r"def m1(){return 32} m1()",32)
        self.e(r"def m1():u64{return 32:u64} m1()",32)
        self.e(r"def m1(x){if x==1 return 32; 64} m1(1)",32)
        self.e(r"def m1(x){if x==1 return 32; 64} m1(0)",64)
        self.e(r"def m1(x){if x==1 return 32 else return 64} m1(1)",32)
        self.e(r"def m1(x){if x==1 return 32 else return 64} m1(0)",64)
        self.ex(AkiTypeErr, r"def m1():u64{return 32} m1()")

    def test_select(self):
        p0 = r"""
def main(){
    var x="Hello"
    var y:i64
    select type(x) {
        case i32{
            y=1:i64
        }
        case type(y){
            y=2:i64
        }
        default {
            y=3:i64
        }
    }
    y
}
main()"""
        p1 = r"""
def main(){
    var x=2
    var y:i64
    select type(x) {
        case i32{
            y=1:i64
        }
        case type(y){
            y=2:i64
        }
    }
    y
}
main()"""
        p2 = r"""
def main(){
    var x=2
    var y:i64
    select x {
        case type(y){
            y=2:i64
        }
    }
    y
}
main()"""

        p3 = r"""
def main(){
    var x=2, y=0
    select x {
        case 3
            y=0
        case 4
            y=1
        default
            y=2
        default
            y=3
    }
}
"""
        self.e(p0, 3)
        self.e(p1, 1)
        self.ex(AkiTypeErr, p2)
        self.ex(AkiSyntaxErr, p3)

