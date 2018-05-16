from ctypes import CFUNCTYPE, c_int32, c_double
from collections import namedtuple
import colorama
colorama.init()
from termcolor import colored, cprint
from ast_module import *
from parsing import *
from codegen import *
from errors import *
from repl import paths
from vartypes import Str

Result = namedtuple("Result", ['value', 'ast', 'rawIR', 'optIR'])


def dump(str, filename):
    """Dump a string to a file name."""
    with open(filename, 'w') as file:
        file.write(str)


def lastIR(module, index=-1):
    """Returns the last bunch of code added to a module. 
    Thus gets the lastly generated IR for the top-level expression"""
    return str(module).split('\n\n')[index]


class AkilangEvaluator(object):
    """Evaluator for Akilang expressions.
    Once an object is created, calls to evaluate() add new expressions to the
    module. Definitions (including externs) are only added into the IR - no
    JIT compilation occurs. When a toplevel expression is evaluated, the whole
    module is JITed and the result of the expression is returned.
    """

    def __init__(self, basiclib_file=None):
        llvm.initialize()
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()

        #llvm.load_library_permanently('freeglut.dll')
        #llvm.load_library_permanently('ucrtbase.dll')

        self.basiclib_file = basiclib_file
        self.target = llvm.Target.from_default_triple()
        self.reset()

    def reset(self, history=[]):
        self._reset_base()

        if self.basiclib_file:
            # Load basic language library
            try:
                with open(self.basiclib_file) as file:
                    for result in self.eval_generator(file.read()):
                        pass
            except (FileNotFoundError, ParseError, CodegenError) as err:
                print(
                    colored(f"Could not load basic library: {err}", 'red'),
                    self.basiclib_file)
                self._reset_base()
                raise

        #with open('llvmlib.ll') as file:
        #self.eval_llasm(file.read())

        if history:
            # Run history
            try:
                for ast in history:
                    self._eval_ast(ast)
            except CodegenError:
                print(
                    colored("Could not run history:", 'red'),
                    self.basiclib_file)
                self._reset_base()

    def _reset_base(self):
        self.codegen = LLVMCodeGenerator()
        self._add_builtins(self.codegen.module)

    def evaluate(self, codestr, options=dict()):
        """Evaluates only the first top level expression in codestr.
        Assume there is only one expression. 
        To evaluate all expressions, use eval_generator."""
        return next(self.eval_generator(codestr, options)).value

    def eval_generator(self, codestr, options=dict()):
        """Iterator that evaluates all top level expression in codestr.
        Yield a namedtuple Result with None for definitions and externs, and the evaluated expression
        value for toplevel expressions.
        """
        anon_vartype = options.get('anon_vartype', DEFAULT_TYPE)
        for ast in Parser(anon_vartype=anon_vartype).parse_generator(codestr):
            yield self._eval_ast(ast, **options)

    def eval_llasm(self, llvm_asm):
        '''
        Evaluate raw LLVM assembly
        '''
        xx = (str(self.codegen.module) + str(llvm_asm))

        llvmmod = llvm.parse_assembly(xx)
        llvmmod.verify()
        target_machine = self.target.create_target_machine()
        with llvm.create_mcjit_compiler(llvmmod, target_machine) as ee:
            ee.finalize_object()

    def _eval_ast(self,
                  ast,
                  optimize=True,
                  llvmdump=False,
                  noexec=False,
                  parseonly=False,
                  verbose=False,
                  anon_vartype=DEFAULT_TYPE,
                  return_type=c_int32):
        """ 
        Evaluate a single top level expression given in ast form
        
            optimize: activate optimizations

            llvmdump: generated IR and assembly code will be dumped prior to execution.

            noexec: the code will be generated but not executed. Yields non-optimized IR.

            parseonly: the code will only be parsed. Yields an AST dump.

            verbose: yields a quadruplet tuple: result, AST, non-optimized IR, optimized IR
        
        """
        rawIR = None
        optIR = None
        if parseonly:
            return Result(ast.dump(), ast, rawIR, optIR)

        # Generate code
        self.codegen.generate_code(ast)
        if noexec or verbose:
            rawIR = lastIR(self.codegen.module)

        if noexec:
            return Result(rawIR, ast, rawIR, optIR)

        if llvmdump:
            dump(
                str(self.codegen.module),
                f'{paths["dump_dir"]}\\__dump__unoptimized.ll')

        # If we're evaluating a definition or extern declaration, don't do
        # anything else. If we're evaluating an anonymous wrapper for a toplevel
        # expression, JIT-compile the module and run the function to get its
        # result.

        def_or_extern = not ((isinstance(ast, Function) and ast.is_anonymous())
                             #or (isinstance(ast,Uni))
                             )

        if def_or_extern and not verbose:
            return Result(None, ast, rawIR, optIR)

        # Convert LLVM IR into in-memory representation and verify the code
        llvmmod = llvm.parse_assembly(str(self.codegen.module))
        llvmmod.verify()

        # Optimize the module
        if optimize:
            from compiler import optimize
            llvmmod, _ = optimize(llvmmod)
            
            if llvmdump:
                dump(
                    str(llvmmod), f'{paths["dump_dir"]}\\__dump__optimized.ll')

        if verbose:
            optIR = lastIR(llvmmod, -2)
            if def_or_extern:
                return Result(None, ast, rawIR, optIR)

        # Create a MCJIT execution engine to JIT-compile the module. Note that
        # ee takes ownership of target_machine, so it has to be recreated anew
        # each time we call create_mcjit_compiler.
        target_machine = self.target.create_target_machine(
            opt=3, codemodel='large')
        with llvm.create_mcjit_compiler(llvmmod, target_machine) as ee:
            ee.finalize_object()

            if llvmdump:
                dump(
                    target_machine.emit_assembly(llvmmod),
                    f'{paths["dump_dir"]}\\__dump__assembler.asm')
                print(
                    colored(
                        f'Code dumped in local directory {paths["dump_dir"]}',
                        'yellow'))

            if not ast.proto.name.startswith('_ANONYMOUS.'):
                from mangling import mangle_call
                name = mangle_call(ast.proto.name, [])
            else:
                name = ast.proto.name

            fptr = CFUNCTYPE(return_type)(ee.get_function_address(name))

            try:
                result = fptr()
            except OSError as e:
                print (colored(f'OS error: {e}','red'))
                return Result(-1, ast, rawIR, optIR)
            return Result(result, ast, rawIR, optIR)

    def _add_builtins(self, module):
        import os, importlib
        builtins = importlib.import_module(f'stdlib.{os.name}')
        builtins.stdlib(self, module)


#---- Some unit tests ----#

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


if __name__ == '__main__':

    import aki
    aki.run()