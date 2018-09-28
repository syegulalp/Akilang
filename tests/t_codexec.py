import unittest
from ctypes import c_double, c_longlong

from core.codexec import AkilangEvaluator
from core.vartypes import VarTypes
from core.errors import ParseError


ret_u64 = {'return_type': c_double, 'anon_vartype': VarTypes.f64}


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
        self.assertEqual(e.evaluate('ceil(4.5)', ret_u64), 5.0)
        self.assertIsNone(e.evaluate('extern floor(x:f64):f64'))
        self.assertIsNone(
            e.evaluate('def cfadder(x:f64):f64 ceil(x) + floor(x)'))
        self.assertEqual(e.evaluate('cfadder(3.14)', ret_u64), 7.0)

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
        self.assertEqual(e.evaluate('10. % 5.', ret_u64), 5.)
        self.assertEqual(e.evaluate('100. % 5.5', ret_u64), 94.5)

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

        n='''class myClass {
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
        for _ in e.eval_generator(n):
            pass
        self.assertEqual(_.value, 0)

    def test_incr_decr(self):
        e = AkilangEvaluator()
        n = '''
        def main() {
            var x=1, f=1.0, y=0
            x+=1
            if x!=2 then y=1
            x=0
            x-=1
            if x!=-1 then y=1
            f+=1.0
            if f!=2.0 then y=1
            f=0.0
            f-=1.0
            if f!=-1.0 then y=1
            y
        }
        main()
        '''
        for _ in e.eval_generator(n):
            pass
        self.assertEqual(_.value, 0)

    
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
        for _ in e.eval_generator(n):
            pass
        self.assertEqual(_.value, 5)

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
        for _ in e.eval_generator(n):
            pass
        self.assertEqual(_.value, 64)

    def test_strlen_inline(self):
        from core.repl import config
        cfg = config()
        paths = cfg['paths']
        e = AkilangEvaluator(paths['lib_dir'], paths['basiclib'])

        opts = {'return_type': c_longlong, 'anon_vartype': VarTypes.u64}

        e.evaluate('def main():u64{len("Hello there")}')
        self.assertEqual(e.evaluate('main()', opts), 12)
        
        # includes terminating null, do we want that?
    
    def test_auto_free(self):
        '''
        Placeholder. This test is intended to determine if
        automatically allocated resources are freed when
        they go out of scope.
        '''