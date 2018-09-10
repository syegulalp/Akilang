import unittest

from core.codexec import AkilangEvaluator
from ctypes import c_longlong
from core.vartypes import VarTypes

def evallib():
    from core.repl import config
    cfg = config()
    paths = cfg['paths']
    e = AkilangEvaluator(paths['lib_dir'], paths['basiclib'])
    e.reset()
    return e

ret_u64 = {'return_type': c_longlong, 'anon_vartype': VarTypes.u64}

class TestEvaluator(unittest.TestCase):
    def test_c_ref(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def ref(){
                var a=32,
                    b=c_ref(a),
                    c=c_deref(b)
                if a==c then 0 else 1
                }
            ''')
        self.assertEqual(e.evaluate('ref()'), 0)

    def test_c_objref(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def ref(){
                    var a="Hello world", 
                        c=c_obj_ref(a),
                        d=c_obj_deref(c)
                    if cast(c_data(a),u64) == cast(c_data(d),u64)
                        then 0 else 1
                }
            ''')
        self.assertEqual(e.evaluate('ref()'), 0)
    
    def test_c_cast(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def test_cast(){
                var a=128u, b = cast(a,i32)
                if b==128 then 0 else 1
            }            
        ''')
        self.assertEqual(e.evaluate('test_cast()'), 0)

    def test_c_convert(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def test_convert(){
                var a=128, b = convert(a,i64)
                if b==128I then 0 else 1
            }            
        ''')
        self.assertEqual(e.evaluate('test_convert()'), 0)  

    def test_c_cast_int_float(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def test_cast(){
                var a=128, b = cast(a,f64)
                if b==128.0 then 0 else 1
            }            
        ''')
        self.assertEqual(e.evaluate('test_cast()'), 0)

    def test_c_convert_int_float(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def main(){
                var a=128, b = convert(a,f64)
                if b==128.0 then 0 else 1
            }            
        ''')
        self.assertEqual(e.evaluate('main()'), 0)

    def test_alloc_free(self):
        e=evallib()
        e.evaluate('''
        def main(){
            var
                x=c_obj_alloc({with var q:u64[64] q}),
                y=0U,
                z=0
            x[0]=c_addr(x)
            x[1]=64U
            x[63]=64U
            y=x[1]+x[63]
            z=z+(if y==128U then 0 else 1)
            z=z+(if c_obj_free(x) then 0 else 1)
            z
        }
        ''')
        self.assertEqual(e.evaluate('main()'), 0)

    def test_c_ptr_math(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def main(){
                var x:i32[4]
                x[0]=32
                x[3]=64
                var y=c_ptr_math(c_ref(x[0]),12U)
                c_deref(y)
            }
        ''')
        self.assertEqual(e.evaluate('main()'), 64)

    def test_c_ptr_mod(self):
        e = AkilangEvaluator()
        e.evaluate('''
            def main(){
                var x:i32[4]
                x[0]=32
                var y=c_ptr_math(c_ref(x[0]),12U)
                unsafe {
                    c_ptr_mod(y,128)
                }
                c_deref(y)
            }
        ''')
        self.assertEqual(e.evaluate('main()'), 128)

    def test_c_strlen(self):
        e = evallib()
        e.evaluate('''
            def main():u64{
                var x="Hi there"
                len(x)
            }
        ''')
        self.assertEqual(e.evaluate('main()', ret_u64), 9)
