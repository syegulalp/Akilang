import unittest
from ctypes import c_double, c_longlong

from core.codexec import AkilangEvaluator
from core.vartypes import VarTypes
from core.errors import ParseError, CodegenError


class TestEvaluator(unittest.TestCase):
    def test_basic(self):
        e = AkilangEvaluator()
        self.assertEqual(e.evaluate('3'), 3)
        self.assertEqual(e.evaluate('3+3*4'), 15)

    def test_use_func(self):
        e = AkilangEvaluator()
        self.assertIsNone(e.evaluate('def adder(x, y) x+y'))
        self.assertEqual(e.evaluate('adder(5, 4) + adder(3, 2)'), 14)

    def test_use_libc(self):
        e = AkilangEvaluator()
        self.assertIsNone(e.evaluate('extern ceil(x:f64):f64'))
        self.assertEqual(e.evaluate('ceil(4.5F)'), 5.0)
        self.assertIsNone(e.evaluate('extern floor(x:f64):f64'))
        self.assertIsNone(
            e.evaluate('def cfadder(x:f64):f64 ceil(x) + floor(x)'))
        self.assertEqual(e.evaluate('cfadder(3.14F)'), 7.0)

    def test_basic_if(self):
        e = AkilangEvaluator()
        e.evaluate('def foo(a, b) a * if a < b then a + 1 else b + 1')
        self.assertEqual(e.evaluate('foo(3, 4)'), 12)
        self.assertEqual(e.evaluate('foo(5, 4)'), 25)

    def test_nested_if(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def foo(a, b, c)
                if a < b then
                    if a < c then a * 2 else c * 2
                    else b * 2''')
        self.assertEqual(e.evaluate('foo(1, 20, 300)'), 2)
        self.assertEqual(e.evaluate('foo(10, 2, 300)'), 4)
        self.assertEqual(e.evaluate('foo(100, 2000, 30)'), 60)

    def test_nested_if2(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def min3(a, b, c)
                if a < b then
                    if a < c then
                        a 
                        else c
                    elif b < c then 
                        b 
                        else c
            ''')
        self.assertEqual(e.evaluate('min3(1, 2, 3)'), 1)
        self.assertEqual(e.evaluate('min3(1, 3, 2)'), 1)
        self.assertEqual(e.evaluate('min3(2, 1, 3)'), 1)
        self.assertEqual(e.evaluate('min3(2, 3, 1)'), 1)
        self.assertEqual(e.evaluate('min3(3, 1, 2)'), 1)
        self.assertEqual(e.evaluate('min3(3, 3, 2)'), 2)
        self.assertEqual(e.evaluate('min3(3, 3, 3)'), 3)

    def test_for(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def oddlessthan(n)
                loop (x = 1, x < n, x + 2) x
        ''')
        self.assertEqual(e.evaluate('oddlessthan(100)'), 101)
        self.assertEqual(e.evaluate('oddlessthan(1000)'), 1001)
        self.assertEqual(e.evaluate('oddlessthan(0)'), 1)

    def test_custom_binop(self):
        e = AkilangEvaluator()
        e.evaluate('def binary % (a:f64, b:f64):f64 a - b')
        self.assertEqual(e.evaluate('10. % 5.',), 5.)
        self.assertEqual(e.evaluate('100. % 5.5',), 94.5)

    def test_custom_unop(self):
        e = AkilangEvaluator()
        e.evaluate('def unary !(a) 0 - a')
        e.evaluate('def unary ^(a) a * a')
        self.assertEqual(e.evaluate('!10'), -10)
        self.assertEqual(e.evaluate('^10'), 100)
        self.assertEqual(e.evaluate('!^10'), -100)
        self.assertEqual(e.evaluate('^!10'), 100)

    def test_mixed_ops(self):
        e = AkilangEvaluator()
        e.evaluate('def unary!(a) 0 - a')
        e.evaluate('def unary^(a) a * a')
        e.evaluate('def binary %(a, b) a - b')
        self.assertEqual(e.evaluate('!10 % !20'), 10)
        self.assertEqual(e.evaluate('^(!10 % !20)'), 100)

    def test_var_expr1(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def foo(x, y, z){
                var s1 = x + y, s2 = z + y
                s1 * s2
            }
            ''')
        self.assertEqual(e.evaluate('foo(1, 2, 3)'), 15)

    def test_var_expr2(self):
        e = AkilangEvaluator()
        e.evaluate('def binary ; 1 (x, y) y')
        e.evaluate('''
            def foo(step) {
                var accum=0
                loop (i = 0, i < 10, i + step)
                    accum = accum + i
                accum
            }
            ''')
        self.assertEqual(e.evaluate('foo(2)'), 20)

    def test_nested_var_exprs(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def foo(x y z) {
                with var s1 = x + y, s2 = z + y {
                    with var s3 = s1 * s2 {
                        s3 * 100
                    }
                }
            }
            ''')
        self.assertEqual(e.evaluate('foo(1, 2, 3)'), 1500)

    def test_assignments(self):
        e = AkilangEvaluator()
        e.evaluate('def binary ; 1 (x, y) y')
        e.evaluate('''
            def foo(a b) {
                var s, p, r
                s = a + b ;
                p = a * b ;
                r = s + 100 * p
                r
            }
            ''')
        self.assertEqual(e.evaluate('foo(2, 3)'), 605)
        self.assertEqual(e.evaluate('foo(10, 20)'), 20030)

    def test_triple_assignment(self):
        e = AkilangEvaluator()
        e.evaluate('def binary ; 1 (x, y) y')
        e.evaluate('''
            def foo(a) {
                var x, y, z
                x = y = z = a
                ; x + 2 * y + 3 * z
            }
            ''')
        self.assertEqual(e.evaluate('foo(5)'), 30)

    def test_array_assignment(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def main(){
                var a:i32[3,32,32]
                a[0,8,16]=1
                a[1,31,16]=2
                a[2,0,0]=4
                return a[0,8,16]+a[1,31,16]+a[2,0,0]
            }
        ''')
        self.assertEqual(e.evaluate('main()'), 7)

    def test_uni_assignment(self):
        e = AkilangEvaluator()
        e.evaluate('''
            uni {
                a:i32[3,32,32],
                b:i32
            }
        ''')
        e.evaluate('''
            def main(){
                b=32
                a[0,8,16]=1
                a[1,31,16]=2
                a[2,0,0]=4
                return a[0,8,16]+a[1,31,16]+a[2,0,0]+b
            }            
        ''')
        self.assertEqual(e.evaluate('main()'), 39)

    def test_type_value_trapping(self):
        e = AkilangEvaluator()
        try:
            e.evaluate('cast(32,print)')
        except ParseError as e:
            pass

    def test_optargs(self):
        e = AkilangEvaluator()
        e.evaluate('def f1(x:i32, y:i32=32, z:byte=1B) y')
        e.evaluate('def f2(x:i32=1) x')
        e.evaluate('def main(){f1(4)+f1(1,2)+f2()+f2(8)}')
        self.assertEqual(e.evaluate('main()'), 43)

    def test_class_assignment(self):
        e = AkilangEvaluator()

        n = '''class myClass {
                x:i32
                prop:u32
                other:u32
                string:str
            }
            def fn2(x:myClass, x1:i32, s1:str): myClass{
                x.string=s1
                x.x=x1
                return x
            }
            def main(){
                var c1:myClass
                var z=0
                var c2="Hi you"
                c1 = fn2(c1, 64, c2)
                z = z + (if c1.x == 64 then 0 else 1)
                z = z + (if c_data(c1.string)==c_data(c2) then 0 else 1)
                return z
            }
            main()
            '''
        self.assertEqual(e.eval_all(n), 0)

    def test_incr_decr(self):
        e = AkilangEvaluator()
        n = '''
        def main() {
            var x=1, f=1.0, y=0
            x+=1
            when x!=2 then y=1
            x=0
            x-=1
            when x!=-1 then y=1
            f+=1.0
            when f!=2.0 then y=1
            f=0.0
            f-=1.0
            when f!=-1.0 then y=1
            y
        }
        main()
        '''
        self.assertEqual(e.eval_all(n), 0)

    def test_continue_and_break(self):
        e = AkilangEvaluator()
        n = '''
        def main() {
            var x=1,y=1
            loop {
                x+=1
                if x<10 then continue
                y=0
                break
            }
            y+x
        }
        main()
        '''
        self.assertEqual(e.eval_all(n), 10)

    def test_function_pointer(self):
        e = AkilangEvaluator()
        n = '''
        @varfunc {
            def f1(a:i32):i32 {
                a+1
            }

            def f2(a:i32):i32{
                a+2
            }
        }

        def main(){
            var f:func(i32):i32
            var z
            f=f1
            z=z+f(1)
            f=f2
            z=z+f(1)
            z
        }

        main()'''

        self.assertEqual(e.eval_all(n), 5)

    def test_object_pass_array(self):
        e = AkilangEvaluator()
        n = '''
        def fn1(x:i32[8]) :i32[8] {
            x[0]=64
            return x
        }

        def main(){
            var xx:i32[8]
            xx[0]=32
            fn1(xx)
            xx[0]
        }

        main()'''

        self.assertEqual(e.eval_all(n), 64)

    def test_constant_promotion(self):
        e = AkilangEvaluator()

        # autopromote i1 to i64
        self.assertEqual(e.eval_all('1b+4I'), 5)

        # autopromote u8 to u64
        self.assertEqual(e.eval_all('1B+4U'), 5)

        # autopromote i32 to i64
        self.assertEqual(e.eval_all('4i+4I'), 8)

        # autopromote u32 to i64 (invalid)
        with self.assertRaises(CodegenError):
            e.eval_all('4u+4I')

    def test_int_to_str_and_back(self):
        e = AkilangEvaluator(True)

        n = '''
        def str_to_int(){
            var x="32767"
            var y=i32(x)
            y
        }
        str_to_int()
        '''

        self.assertEqual(e.eval_all(n), 32767)

        n = '''
        def int_to_str():u64{
            var x=32767
            var y=str(x)
            len(y)
        }
        int_to_str()
        '''

        self.assertEqual(e.eval_all(n), 5)

        n = '''
        def int_to_str_and_back(){
            var x=32767
            var y=str(x)
            var z=i32(y)
            z
        }
        int_to_str_and_back()
        '''

        self.assertEqual(e.eval_all(n), 32767)

        n = '''
        def str_to_int_and_back():u64{
            var x="32767"
            var y=i32(x)
            var z=str(y)
            len(z)
        }
        str_to_int_and_back()
        '''

        self.assertEqual(e.eval_all(n), 5)

    def test_string_behaviors(self):
        e = AkilangEvaluator(True)
        
        # return from REPL
        self.assertEqual(e.eval_all("'Hi there'"), '"Hi there"')
        # slicing
        self.assertEqual(e.eval_all("{var x='Hi there' x[1]}"), 105)
        # slicing inine instance
        self.assertEqual(e.eval_all('"Hi there"[1]'), 105)
        # string length
        self.assertEqual(
            e.evaluate('len("Hello there")'),
            12
        )

    def test_zeroinit(self):
        e = AkilangEvaluator()
        n='''
        def main():u64{
            var x:ptr byte
            var x2=c_ptr_int(x)
            x2
        }
        main()
        '''
        self.assertEqual(e.eval_all(n), 0)

        n='''
        def m2(){
            var x
            x
        }
        m2()
        '''
        self.assertEqual(e.eval_all(n), 0)

        n='''
        def m3():f64{
            var x:f64
            x
        }
        m3()
        '''
        self.assertEqual(e.eval_all(n), 0.0)

    def test_pragma(self):
        # TODO: This isn't yet a very robust test
        # It doesn't yet check that the pragmas
        # in the module are in fact set
        # It's mostly to make sure pragmas are 
        # parsed 

        e = AkilangEvaluator(True)
        n = '''
        pragma {    
            unroll_loops = True
            loop_vectorize = True
            diaml = 32
            whatever = 'thingy'
        }'''

        self.assertEqual(e.eval_all(n), None)
    
    def test_array_type_coercion(self):

        # test dimensioned return, implicit and explicit

        e= AkilangEvaluator(True)
        n = '''
        def fn1(x:i32[]):i32[] {
            x[12]=64
            return x
        }

        def fn0(x:i32[]):i32[] {
            x[6]=32
            x
        }

        def main(){
            var y:i32=0
            var xx:i32[31]
            fn1(xx)
            y+=xx[12]
            var zz:i32[16]
            fn0(zz)
            y+=zz[6]

        }
        main()
        '''
        self.assertEqual(e.eval_all(n), 64+32)

        # test dimensionless return, both explicit and implicit

        # TODO: make this test pass
        # w/o the use of explicit obj alloc

        n = '''        
        @track
        def fn2():i32[] {
            var x=c_obj_alloc(i32[12])
            #c_obj_alloc(with var _:i32[12]{_})
            x[6]=64
            return x
        }

        @track
        def fn3():i32[] {
            #var x=c_obj_alloc(with var _:i32[12]{_})
            var x=c_obj_alloc(i32[12])
            x[3]=32
            x
        }

        def main(){
            var y:i32=0
            var xx=fn2()
            y+=xx[6]
            var xy=fn3()
            y+=xy[3]
            y
        }

        main()
        '''
        self.assertEqual(e.eval_all(n), 64+32)

        # test conversion of dimensionless array to dimensioned array
        # using `unsafe` assignment

        n= '''
        @track
        def fn4():i32[] {
            #var x=c_obj_alloc(with var _:i32[12,12,12]{_})
            var x=c_obj_alloc(i32[12,12,12])
            x[0,0,6]=48
            x
        }

        def main(){
            var y:i32[12,12,12]
            unsafe y=fn4()
            y[0,0,6]
        }
        main()
        '''

        self.assertEqual(e.eval_all(n), 48)
    
    def test_array_constant_init(self):

        e= AkilangEvaluator()
        n = '''
        def main(){
        var result=0

        var x:i32[20]=[8,16,24]
        x[1]=32
        if x[0]+x[1]+x[2]!=64 then result+=1

        var y:f64[20]=[8.0F,16.0F,24.0F]
        y[1]=32.0F
        if y[0]+y[1]+y[2]!=64.0F then result+=1

        result
        }
        main()
        '''
        self.assertEqual(e.eval_all(n), 0)
    
    def test_auto_free(self):
        '''
        Placeholder. This test is intended to determine if
        automatically allocated resources are freed when
        they go out of scope.
        '''
