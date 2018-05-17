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



if __name__ == '__main__':

    import aki
    aki.run()