from codexec import *

import unittest

eval_opts = {'return_type': c_double, 'anon_vartype': VarTypes.f64}


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
        eval_opts = {'return_type': c_double, 'anon_vartype': VarTypes.f64}
        self.assertIsNone(e.evaluate('extern ceil(x:f64):f64'))
        self.assertEqual(e.evaluate('ceil(4.5)', eval_opts), 5.0)
        self.assertIsNone(e.evaluate('extern floor(x:f64):f64'))
        self.assertIsNone(
            e.evaluate('def cfadder(x:f64):f64 ceil(x) + floor(x)'))
        self.assertEqual(e.evaluate('cfadder(3.14)', eval_opts), 7.0)

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
        self.assertEqual(e.evaluate('10. % 5.', eval_opts), 5.)
        self.assertEqual(e.evaluate('100. % 5.5', eval_opts), 94.5)

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
            def foo(x, y, z)
                var s1 = x + y, s2 = z + y in
                    s1 * s2
            ''')
        self.assertEqual(e.evaluate('foo(1, 2, 3)'), 15)

    def test_var_expr2(self):
        e = AkilangEvaluator()
        e.evaluate('def binary ; 1 (x, y) y')
        e.evaluate('''
            def foo(step) {
                let accum=0
                loop (i = 0, i < 10, i + step)
                    accum = accum + i
                accum
            }
            ''')
        self.assertEqual(e.evaluate('foo(2)'), 20)

    def test_nested_var_exprs(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def foo(x y z)
                var s1 = x + y, s2 = z + y in
                    var s3 = s1 * s2 in
                        s3 * 100
            ''')
        self.assertEqual(e.evaluate('foo(1, 2, 3)'), 1500)

    def test_assignments(self):
        e = AkilangEvaluator()
        e.evaluate('def binary ; 1 (x, y) y')
        e.evaluate('''
            def foo(a b)
                var s, p, r in
                   s = a + b ;
                   p = a * b ;
                   r = s + 100 * p :
                   r
            ''')
        self.assertEqual(e.evaluate('foo(2, 3)'), 605)
        self.assertEqual(e.evaluate('foo(10, 20)'), 20030)

    def test_triple_assignment(self):
        e = AkilangEvaluator()
        e.evaluate('def binary ; 1 (x, y) y')
        e.evaluate('''
            def foo(a)
                var x, y, z in {
                   x = y = z = a
                   ; x + 2 * y + 3 * z
                }
            ''')
        self.assertEqual(e.evaluate('foo(5)'), 30)

    def test_c_ref(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def ref(){
                let a=32
                let b=c_ref(a)
                let c=c_deref(b)
                if a==c then 1 else 0
                }
            ''')
        self.assertEqual(e.evaluate('ref()'),1)

    def test_c_objref(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def ref(){
                    let a="Hello world"
                    let c=c_obj_ref(a)
                    let d=c_obj_deref(c)
                    if cast(c_data(a),u64) == cast(c_data(d),u64)
                        then 1 else 0
                }
            ''')
        self.assertEqual(e.evaluate('ref()'),1)
