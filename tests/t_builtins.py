import unittest

from core.codexec import AkilangEvaluator

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
                var a=128U, b = cast(a,i32)
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

    def test_alloc_free(self):
        from core.repl import config
        cfg = config()
        paths = cfg['paths']
        e = AkilangEvaluator(paths['lib_dir'], paths['basiclib'])
        e.reset()

        e.evaluate('''
        def main(){
            var
                x=c_obj_alloc({with var z:u64[64] z}),
                y=0U,
                z=0
            x[0]=c_addr(x)
            x[1]=64U
            x[64]=64U
            y=x[1]+x[64]
            z=z+(if y==128U then 0 else 1)
            z=z+(if c_obj_free(x) then 0 else 1)
            z
        }
        ''')
        self.assertEqual(e.evaluate('main()'), 0)