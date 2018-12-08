import unittest
import llvmlite.binding as llvm

from tests import e, e2
from core.repl import paths
from os import path

class TestEvaluator(unittest.TestCase):
    e2=e2

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    
    def _test_compile(self,filename):        
        self.e2.reset()
        with open(path.join(paths['source_dir'],f'{filename}.aki'), encoding='utf-8') as f:
            self.e2.eval_all(f.read())
        llvmmod = llvm.parse_assembly(str(self.e2.codegen.module))
        llvmmod.verify()

    def test_compile_fb(self):
        self._test_compile('fb')

    def test_compile_fib(self):
        self._test_compile('fib')

    def test_compile_hello(self):
        self._test_compile('hello')
    
    def test_compile_life(self):
        self._test_compile('l')

    def test_compile_msg(self):
        self._test_compile('msg')

    def test_compile_robots(self):
        self._test_compile('robots')