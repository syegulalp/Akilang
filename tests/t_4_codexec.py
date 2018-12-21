import unittest
from ctypes import c_double, c_longlong

from core.codexec import AkilangEvaluator
from core.errors import ParseError, CodegenError

from tests import e, e2

from core.utils.redirect import stdout_redirector

class TestEvaluator(unittest.TestCase):
    e = e
    e2 = e2

    def test_basic(self):
        self.e.reset()
        self.assertEqual(self.e.evaluate('3'), 3)
        self.assertEqual(self.e.evaluate('3+3*4'), 15)

    def test_use_func(self):
        self.e.reset()
        self.assertIsNone(self.e.evaluate('def adder(x, y) x+y'))
        self.assertEqual(self.e.evaluate('adder(5, 4) + adder(3, 2)'), 14)

    def test_use_libc(self):
        self.e.reset()
        self.assertIsNone(self.e.evaluate('extern ceil(x:f64):f64'))
        self.assertEqual(self.e.evaluate('ceil(4.5F)'), 5.0)
        self.assertIsNone(self.e.evaluate('extern floor(x:f64):f64'))
        self.assertIsNone(
            self.e.evaluate('def cfadder(x:f64):f64 ceil(x) + floor(x)'))
        self.assertEqual(self.e.evaluate('cfadder(3.14F)'), 7.0)

    def test_basic_if(self):
        self.e.reset()
        self.e.evaluate('def foo(a, b) a * if a < b then a + 1 else b + 1')
        self.assertEqual(self.e.evaluate('foo(3, 4)'), 12)
        self.assertEqual(self.e.evaluate('foo(5, 4)'), 25)

    def test_nested_if(self):
        self.e.reset()
        self.e.evaluate('''
            def foo(a, b, c)
                if a < b then
                    if a < c then a * 2 else c * 2
                    else b * 2''')
        self.assertEqual(self.e.evaluate('foo(1, 20, 300)'), 2)
        self.assertEqual(self.e.evaluate('foo(10, 2, 300)'), 4)
        self.assertEqual(self.e.evaluate('foo(100, 2000, 30)'), 60)

    def test_nested_if2(self):
        self.e.reset()
        self.e.evaluate('''
            def min3(a, b, c)
                if a < b then
                    if a < c then
                        a 
                        else c
                    elif b < c then 
                        b 
                        else c
            ''')
        self.assertEqual(self.e.evaluate('min3(1, 2, 3)'), 1)
        self.assertEqual(self.e.evaluate('min3(1, 3, 2)'), 1)
        self.assertEqual(self.e.evaluate('min3(2, 1, 3)'), 1)
        self.assertEqual(self.e.evaluate('min3(2, 3, 1)'), 1)
        self.assertEqual(self.e.evaluate('min3(3, 1, 2)'), 1)
        self.assertEqual(self.e.evaluate('min3(3, 3, 2)'), 2)
        self.assertEqual(self.e.evaluate('min3(3, 3, 3)'), 3)

    def test_for(self):
        self.e.reset()
        self.e.evaluate('''
            def oddlessthan(n)
                loop (x = 1, x < n, x + 2) x
        ''')
        self.assertEqual(self.e.evaluate('oddlessthan(100)'), 101)
        self.assertEqual(self.e.evaluate('oddlessthan(1000)'), 1001)
        self.assertEqual(self.e.evaluate('oddlessthan(0)'), 1)

    def test_custom_binop(self):
        self.e.reset()
        self.e.evaluate('def binary % (a:f64, b:f64):f64 a - b')
        self.assertEqual(self.e.evaluate('10. % 5.',), 5.)
        self.assertEqual(self.e.evaluate('100. % 5.5',), 94.5)

    def test_custom_unop(self):
        self.e.reset()
        self.e.evaluate('def unary !(a) 0 - a')
        self.e.evaluate('def unary ^(a) a * a')
        self.assertEqual(self.e.evaluate('!10'), -10)
        self.assertEqual(self.e.evaluate('^10'), 100)
        self.assertEqual(self.e.evaluate('!^10'), -100)
        self.assertEqual(self.e.evaluate('^!10'), 100)

    def test_mixed_ops(self):
        self.e.reset()
        self.e.evaluate('def unary!(a) 0 - a')
        self.e.evaluate('def unary^(a) a * a')
        self.e.evaluate('def binary %(a, b) a - b')
        self.assertEqual(self.e.evaluate('!10 % !20'), 10)
        self.assertEqual(self.e.evaluate('^(!10 % !20)'), 100)

    def test_var_expr1(self):
        self.e.reset()
        self.e.evaluate('''
            def foo(x, y, z){
                var s1 = x + y, s2 = z + y
                s1 * s2
            }
            ''')
        self.assertEqual(self.e.evaluate('foo(1, 2, 3)'), 15)

    def test_var_expr2(self):
        self.e.reset()
        self.e.evaluate('def binary ; 1 (x, y) y')
        self.e.evaluate('''
            def foo(step) {
                var accum=0
                loop (i = 0, i < 10, i + step)
                    accum = accum + i
                accum
            }
            ''')
        self.assertEqual(self.e.evaluate('foo(2)'), 20)

    def test_nested_var_exprs(self):
        self.e.reset()
        self.e.evaluate('''
            def foo(x y z) {
                with var s1 = x + y, s2 = z + y {
                    with var s3 = s1 * s2 {
                        s3 * 100
                    }
                }
            }
            ''')
        self.assertEqual(self.e.evaluate('foo(1, 2, 3)'), 1500)

    def test_assignments(self):
        self.e.reset()
        self.e.evaluate('def binary ; 1 (x, y) y')
        self.e.evaluate('''
            def foo(a b) {
                var s, p, r
                s = a + b ;
                p = a * b ;
                r = s + 100 * p
                r
            }
            ''')
        self.assertEqual(self.e.evaluate('foo(2, 3)'), 605)
        self.assertEqual(self.e.evaluate('foo(10, 20)'), 20030)

    def test_triple_assignment(self):
        self.e.reset()
        self.e.evaluate('def binary ; 1 (x, y) y')
        self.e.evaluate('''
            def foo(a) {
                var x, y, z
                x = y = z = a
                ; x + 2 * y + 3 * z
            }
            ''')
        self.assertEqual(self.e.evaluate('foo(5)'), 30)

    def test_array_assignment(self):
        self.e2.reset()
        self.e2.evaluate('''
            def main(){
                var a:i32[3,32,32]
                a[0,8,16]=1
                a[1,31,16]=2
                a[2,0,0]=4
                return a[0,8,16]+a[1,31,16]+a[2,0,0]
            }
        ''')
        self.assertEqual(self.e2.evaluate('main()'), 7)

    def test_uni_assignment(self):
        self.e.reset()
        n='''
            uni {
                a:i32[3,32,32],
                b:i32
            }

            def main(){
                b=32
                a[0,8,16]=1
                a[1,31,16]=2
                a[2,0,0]=4
                return a[0,8,16]+a[1,31,16]+a[2,0,0]+b
            }            
        
            main()
        '''
        self.assertEqual(self.e.eval_all(n), 39)

    def test_const_assignment(self):
        self.e.reset()
        n = '''
        const {
            a=32,
            b=a+32
        }
        def main(){
            a+b
        }
        main()
        '''
        self.assertEqual(self.e.eval_all(n),96)

    def test_type_value_trapping(self):
        self.e.reset()
        try:
            self.e.evaluate('cast(32,print)')
        except ParseError as e:
            pass

    def test_optargs(self):
        self.e.reset()
        self.e.evaluate('def f1(x:i32, y:i32=32, z:byte=1B) y')
        self.e.evaluate('def f2(x:i32=1) x')
        self.e.evaluate('def main(){f1(4)+f1(1,2)+f2()+f2(8)}')
        self.assertEqual(self.e.evaluate('main()'), 43)

    def test_class_assignment(self):
        self.e2.reset()

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
        self.assertEqual(self.e2.eval_all(n), 0)

    def test_incr_decr(self):
        self.e.reset()
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
        self.assertEqual(self.e.eval_all(n), 0)

    def test_continue_and_break(self):
        self.e.reset()
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
        self.assertEqual(self.e.eval_all(n), 10)

    def test_function_pointer(self):
        self.e2.reset()
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

        self.assertEqual(self.e2.eval_all(n), 5)

    def test_object_pass_array(self):
        self.e2.reset()
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

        self.assertEqual(self.e2.eval_all(n), 64)

    def test_constant_promotion(self):
        #self.e.reset()
        self.e.reset()

        # autopromote i1 to i64
        self.assertEqual(self.e.eval_all('1b+4I'), 5)

        # autopromote u8 to u64
        self.assertEqual(self.e.eval_all('1B+4U'), 5)

        # autopromote i32 to i64
        self.assertEqual(self.e.eval_all('4i+4I'), 8)

        # autopromote u32 to i64 (invalid)
        with self.assertRaises(CodegenError):
            self.e.eval_all('4u+4I')

    def test_int_to_str_and_back(self):
        
        self.e2.reset()

        n = '''
        def str_to_int(){
            var x="32767"
            var y=i32(x)
            y
        }
        str_to_int()
        '''

        self.assertEqual(self.e2.eval_all(n), 32767)

        n = '''
        def int_to_str():u64{
            var x=32767
            var y=str(x)
            len(y)
        }
        int_to_str()
        '''

        self.assertEqual(self.e2.eval_all(n), 5)

        n = '''
        def int_to_str_and_back(){
            var x=32767
            var y=str(x)
            var z=i32(y)
            z
        }
        int_to_str_and_back()
        '''

        self.assertEqual(self.e2.eval_all(n), 32767)

        n = '''
        def str_to_int_and_back():u64{
            var x="32767"
            var y=i32(x)
            var z=str(y)
            len(z)
        }
        str_to_int_and_back()
        '''

        self.assertEqual(self.e2.eval_all(n), 5)

    def test_string_behaviors(self):
        
        self.e2.reset()

        # return from REPL
        self.assertEqual(self.e2.eval_all("'Hi there'"), '"Hi there"')
        # slicing
        self.assertEqual(self.e2.eval_all("{var x='Hi there' x[1]}"), 105)
        # slicing inine instance
        self.assertEqual(self.e2.eval_all('"Hi there"[1]'), 105)
        # string length
        self.assertEqual(
            self.e2.evaluate('len("Hello there")'),
            12
        )

    def test_zeroinit(self):
        #self.e.reset()
        self.e.reset()
        n = '''
        def main():u64{
            var x:ptr byte
            var x2=c_ptr_int(x)
            x2
        }
        main()
        '''
        self.assertEqual(self.e.eval_all(n), 0)

        n = '''
        def m2(){
            var x
            x
        }
        m2()
        '''
        self.assertEqual(self.e.eval_all(n), 0)

        n = '''
        def m3():f64{
            var x:f64
            x
        }
        m3()
        '''
        self.assertEqual(self.e.eval_all(n), 0.0)

    def test_pragma(self):
        # TODO: This isn't yet a very robust test
        # It doesn't yet check that the pragmas
        # in the module are in fact set
        # It's mostly to make sure pragmas are
        # parsed

        #
        self.e.reset()
        n = '''
        pragma {    
            unroll_loops = True
            loop_vectorize = True
            diaml = 32
            whatever = 'thingy'
        }'''

        self.assertEqual(self.e.eval_all(n), None)

    def test_array_type_coercion(self):

        # test dimensioned return, implicit and explicit

        self.e2.reset()
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
        self.assertEqual(self.e2.eval_all(n), 64+32)

        # test dimensionless return, both explicit and implicit

        # TODO: make this test pass
        # w/o the use of explicit obj alloc

        self.e2.reset()

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
        self.assertEqual(self.e2.eval_all(n), 64+32)

        # test conversion of dimensionless array to dimensioned array
        # using `unsafe` assignment

        self.e2.reset()

        n = '''
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

        self.assertEqual(self.e2.eval_all(n), 48)

    def test_array_constant_init(self):

        #self.e.reset()
        self.e.reset()
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
        self.assertEqual(self.e.eval_all(n), 0)

    def test_array_inline_init(self):
        self.e2.reset()
        n = '''
        def main(){
            var xx:i32[31]
            xx=[8,16,32]
            xx[0]+xx[1]+xx[2]+xx[3]
        }
        main()
        '''
        self.assertEqual(self.e2.eval_all(n), 56)

    def test_array_uni_init(self):
        self.e.reset()
        n = '''
        uni {
            x:i32[3] = [8,16,32]
        }

        def main(){
            x[0]+x[1]+x[2]
        }
        main()
        '''
        self.assertEqual(self.e.eval_all(n),56)

    def test_array_const_init(self):
        self.e.reset()
        n = '''
        const {
            x:i32[3]=[8,16,32]
        }

        def main(){
            x[0]+x[1]+x[2]
        }
        main()
        '''
        self.assertEqual(self.e.eval_all(n),56)

        self.e.reset()
        n = '''
        const {
            x:i32[]=[8,16,32]
        }

        def main(){
            x[0]+x[1]+x[2]
        }
        main()
        '''
        self.assertEqual(self.e.eval_all(n),56)   

        self.e.reset()
        n = '''
        const {
            x=[8,16,32]
        }

        def main(){
            x[0]+x[1]+x[2]
        }
        main()
        '''
        self.assertEqual(self.e.eval_all(n),56)        

    def test_reassign_const_trap(self):
        self.e.reset()
        n = '''
        const {
            x=[8,16,32]
        }
        def main(){
            x[0]+=1
        }'''
        
        with self.assertRaises(CodegenError):
            self.e.eval_all(n)

        self.e.reset()
        n = '''
        const {
            x=1
        }
        def main(){
            x+=1
        }
        main()
        '''
        
        with self.assertRaises(CodegenError):
            self.e.eval_all(n)            
    
    def test_anon_array_init(self):
        self.e.reset()
        self.assertEqual(self.e.evaluate('{var x=[1,2,3] x[2]}'), 3)        

    def test_uni_const_failure(self):
        
        # This should not be allowed
        
        self.e.reset()
        n = '''
        uni {
            y=32
            x:i32[3]=[y,16,32]
        }
        '''
        
        with self.assertRaises(CodegenError):
            self.e.eval_all(n)


    def test_array_const_init_with_compile_time_eval(self):
        
        # This should not be permitted
        
        self.e.reset()
        n = '''
        const {
            y=8
            x:i32[3]=[y,16,32]
        }

        def main(){
            x[0]+=1
            x[0]
        }
        main()
        '''        

        with self.assertRaises(CodegenError):
            self.e.eval_all(n)
        
        self.e.reset()

        # This, however, is okay

        n = '''
        const {
            y=8
            x:i32[3]=[y,16,32]
        }

        uni {
            z=8
            t:i32[3]=[y,16,32]
        }

        def main(){
            t[0]+=1
            x[0]+x[1]+x[2]+
                t[0]+t[1]+t[2]
        }
        main()
        '''
        self.assertEqual(self.e.eval_all(n),113)

    def test_array_uni_init_extend(self):
        self.e.reset()
        n = '''
        uni {
            x:i32[4] = [8,16,32]
        }

        def main(){
            x[0]+x[1]+x[2]+x[3]
        }
        main()
        '''
        self.assertEqual(self.e.eval_all(n),56)

    def test_type_enum(self):
        self.e.reset()
        self.assertEqual(self.e.evaluate('type("Hi")==type(str)'), 1)
        self.assertEqual(self.e.evaluate('type(32)==type(i32)'), 1)
        self.assertEqual(self.e.evaluate('type(32u)==type(u32)'), 1)
        self.assertEqual(self.e.evaluate('type(32U)==type(u64)'), 1)
        self.assertEqual(self.e.evaluate('type(1b)==type(0b)'), 1)
        self.assertEqual(self.e.evaluate('type(1.0)==type(0.00)'), 1)
        self.assertEqual(self.e.evaluate('type(i32[20])==type(array)'), 0)
        self.assertEqual(self.e.evaluate('type(i32[20])==type(i32[64])'), 1)
        self.assertEqual(self.e.evaluate('type([20])==type([64])'), 1)
        self.assertEqual(self.e.evaluate('type([20])==type(carray)'), 1)
        
        # TODO: func enums should be distinct by type
        # self.assertEqual(self.e.evaluate('type(func(i32):i32)==type(func)'), 0)


    def test_isinstance(self):
        self.e.reset()
        self.assertEqual(self.e.evaluate('isinstance("Hi",str)'), 1)
        self.assertEqual(self.e.evaluate('isinstance("Hi",obj)'), 1)
        self.assertEqual(self.e.evaluate('isinstance(32,i32)'), 1)
        self.assertEqual(self.e.evaluate('isinstance(32,int)'), 1)
        self.assertEqual(self.e.evaluate('isinstance(32u, u32)'), 1)
        self.assertEqual(self.e.evaluate('isinstance(32U, u64)'), 1)
        
        self.assertEqual(self.e.evaluate('isinstance(1.0F, f64)'), 1)
        self.assertEqual(self.e.evaluate('isinstance(1.0f, f32)'), 1)
        self.assertEqual(self.e.evaluate('isinstance(i32[20], array)'), 1)
        self.assertEqual(self.e.evaluate('isinstance(i32[20], obj)'), 1)
        self.assertEqual(self.e.evaluate('isinstance(i32[20], i32[64])'), 1)
        self.assertEqual(self.e.evaluate('isinstance([20], carray)'), 1)
        self.assertEqual(self.e.evaluate('isinstance([20], array)'), 0)
        self.assertEqual(self.e.evaluate('isinstance(func(i32):i32, func)'), 1)

        self.e2.reset()
        self.assertEqual(self.e2.evaluate('isinstance(True, bool))'), 1)

    def test_box_type(self):
        self.e2.reset()
        self.assertEqual(self.e2.evaluate('objtype(box("Hi"))==type(str)'), 1)
        self.assertEqual(self.e2.evaluate('objtype(box(32))==type(i32)'), 1)
        self.assertEqual(self.e2.evaluate('objtype(box(32u))==type(u32)'), 1)
        self.assertEqual(self.e2.evaluate('objtype(box(32U))==type(u64)'), 1)
        self.assertEqual(self.e2.evaluate('objtype(box(1b))==type(0b)'), 1)
        self.assertEqual(self.e2.evaluate('objtype(box(1.0))==type(0.00)'), 1)
        self.assertEqual(self.e2.evaluate('objtype(box({var x:i32[20] x}))==type(i32[64])'), 1)
        self.assertEqual(self.e2.evaluate('objtype(box({var x:i32[20] x}))==type(array)'), 0)
        self.assertEqual(self.e2.evaluate('objtype(box([20]))==type([64])'), 1)
        self.assertEqual(self.e2.evaluate('objtype(box([20]))==type(carray)'), 1)
    
    def test_unbox_instance_type(self):
        self.e2.reset()
        self.assertEqual(self.e2.evaluate('{var x=box("Hi") isinstance(unbox(x,str,"Yo"), str)}'), 1)
        self.assertEqual(self.e2.evaluate('{var x=box(32) isinstance(unbox(x,i32,0), i32)}'), 1)
        self.assertEqual(self.e2.evaluate('{var x=box(32u) isinstance(unbox(x,u32,0u), u32)}'), 1)
        self.assertEqual(self.e2.evaluate('{var x=box(32U) isinstance(unbox(x,u64,0U), u64)}'), 1)
        self.assertEqual(self.e2.evaluate('{var x=box(1b) isinstance(unbox(x,bool,0b), bool)}'), 1)
        self.assertEqual(self.e2.evaluate('{var x=box(1.0) isinstance(unbox(x,f64,0.0), f64)}'), 1.0)
    
    def test_unbox_type(self):
        # success tests

        self.e2.reset()
        self.assertEqual(self.e2.evaluate('{var x=box("Hi") unbox(x,str,"Yo")}'), '"Hi"')
        self.assertEqual(self.e2.evaluate('{var x=box(32) unbox(x,i32,0)}'), 32)
        self.assertEqual(self.e2.evaluate('{var x=box(32u) unbox(x,u32,0u)}'), 32)
        self.assertEqual(self.e2.evaluate('{var x=box(32U) unbox(x,u64,0U)}'), 32)
        self.assertEqual(self.e2.evaluate('{var x=box(1b) unbox(x,bool,0b)}'), True)
        self.assertEqual(self.e2.evaluate('{var x=box(1.0) unbox(x,f64,0.0)}'), 1.0)
        self.assertEqual(self.e2.evaluate('{var x=box({var y:i32[20]=[1] y}) var z=unbox(x,i32[20],{with var q:i32[20]=[1] q}) z[0]}'), 1)

        # TODO: need to be able to say `unbox(x,i32[64],0)[0]`
        
        # self.assertEqual(self.e2.evaluate('objtype(box([20]))==type(carray)'), 1)
        # TODO: no way to really do this last test yet
        
    def test_unbox_type_failure(self):
        # failure/substitution tests

        self.e2.reset()
        self.assertEqual(self.e2.evaluate('{var x=box(32) unbox(x,str,"Yo")}'), '"Yo"')
        self.assertEqual(self.e2.evaluate('{var x=box(32U) unbox(x,i32,0)}'), 0)
        self.assertEqual(self.e2.evaluate('{var x=box(32) unbox(x,u32,0u)}'), 0)
        self.assertEqual(self.e2.evaluate('{var x=box(32) unbox(x,u64,0U)}'), 0)
        self.assertEqual(self.e2.evaluate('{var x=box(32) unbox(x,bool,0b)}'), False)
        self.assertEqual(self.e2.evaluate('{var x=box(32) unbox(x,f64,0.0)}'), 0.0)
        self.assertEqual(self.e2.evaluate('{var x=box(32) var z=unbox(x,i32[20],{with var q:i32[20]=[1] q}) z[0]}'), 1)        

    def test_unbox_unsafe(self):
        self.e2.reset()
        self.assertEqual(self.e2.evaluate('{var x=box(32) unsafe unbox(x,i32)}'), 32)
        self.assertNotEqual(self.e2.evaluate('{var x=box("Hi!") unsafe unbox(x,i32)}'), 0)


    def test_printing(self):
        import io
        f = io.BytesIO()
        with stdout_redirector(f):
            self.e2.reset()
            self.assertEqual(self.e2.evaluate('{var x=32 print(x)}'), 3)
            self.assertEqual(self.e2.evaluate('print(2+2)'), 2)
            self.assertEqual(self.e2.evaluate('print("Hello")'), 6)
            self.assertEqual(self.e2.evaluate('print(if True then "Hello" else "No")'), 6)
            self.assertEqual(self.e2.evaluate('print(if False then "Hello" else "No")'), 3)

        # this result is number of characters printed, NOT string
        # TODO: return string pointer from print if possible
        # output also needs to be temporarily redirected


    def test_print(self):
        pass
        # https://eli.thegreenplace.net/2015/redirecting-all-kinds-of-stdout-in-python/


        # self.e2.reset()

        # import sys, io, os
        # fd = sys.stdout.fileno()        
        # sys.stdout.flush()       
        
        # new_stdout = io.StringIO()
        # os.dup2(new_stdout.fileno, fd)

        # sys.stdout = os.fdopen(fd, 'w')
        
        # n = 'print("Hi")'
        # self.assertEqual(self.e2.eval_all(n),3)

        # We don't currently have a way to redirect
        # output from the subprocess. sys.stdout does
        # not capture that.        

    def test_incr_decr(self):

        # Disabled for the time being as we rework things.

        self.e2.reset()
        n = '''
        def get_refcount(x:obj):u64 {
            var f1 = c_gep(x,OBJ_REFCOUNT)
            var f2 = c_deref(f1)
            return f2
        }

        def main():u64 {
            var total:u64=0U
            var x=box("Hi")
            total+=get_refcount(x)
            call('.obj..__incr__', x)    
            total+=get_refcount(x)
            call('.obj..__decr__', x)
            total+=get_refcount(x)
            call('.obj..__decr__', x)
            total+=get_refcount(x)
            total
        }
        main()
        '''
        
        #self.assertEqual(self.e2.eval_all(n),1)

    
    def test_auto_free(self):
        '''
        Placeholder. This test is intended to determine if
        automatically allocated resources are freed when
        they go out of scope.
        Not sure how to test this properly yet.
        Possibly by way of raw pointers, etc.
        '''
