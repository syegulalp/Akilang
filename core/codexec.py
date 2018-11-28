from ctypes import CFUNCTYPE, c_int32, c_double, c_void_p, c_char_p, cast, POINTER, string_at
from collections import namedtuple
import colorama
colorama.init()
from termcolor import colored, cprint

from core.parsing import Parser
from core.codegen import llvm, LLVMCodeGenerator
from core.errors import CodegenError, ParseError
from core.repl import paths
from core.vartypes import generate_vartypes

from core.ast_module import Function, Prototype, Do

from time import perf_counter
import os

Result = namedtuple("Result", ['value', 'ast', 'rawIR', 'optIR', 'time'])


def dump(str, filename):
    '''
    Dump a string to a file name.
    '''

    with open(filename, 'w') as file:
        file.write(str)


def lastIR(module, index=-1):
    '''
    Returns the last bunch of code added to a module. 
    This retrieves the most recent generated IR for the top-level expression
    '''

    return str(module).split('\n\n')[index]


class AkilangEvaluator(object):
    '''
    Evaluator for Akilang expressions.
    Once an object is created, calls to evaluate() add new expressions to the
    module. Definitions (including externs) are only added into the IR - no
    JIT compilation occurs. When a toplevel expression is evaluated, the whole
    module is JITed and the result of the expression is returned.
    '''

    def __init__(self, use_default_basiclib=False, basiclib_dir=None, basiclib_file=None, vartypes=None):

        self.cached_lib = []

        if use_default_basiclib:
            from core.repl import config
            cfg = config()
            paths = cfg['paths']
            basiclib_dir = paths['lib_dir']
            basiclib_file = paths['basiclib']

        llvm.initialize()
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()

        # llvm.load_library_permanently('freeglut.dll')
        # llvm.load_library_permanently('ucrtbase.dll')

        if vartypes is None:
            vartypes = generate_vartypes()

        self.vartypes = vartypes  # generate_vartypes()

        self.basiclib_dir = basiclib_dir
        self.basiclib_file = basiclib_file
        self.target = llvm.Target.from_default_triple()
        self.reset()
        
        

    def load_file(self, f):
        try:
            with open(f) as file:
                buf = file.read()
                self.cached_lib.append(buf)
                self.eval_all(buf)
        except (FileNotFoundError, ParseError, CodegenError) as err:
            print(
                colored(f"Could not load basic library: {err}", 'red'),
                f)
            self._reset_base()
            raise err

    def reset(self, history=[]):
        self._reset_base()
        if self.cached_lib:
            for _ in self.cached_lib:
                self.eval_all(_)
            return

        if self.basiclib_dir:

            # First, load the builtins
            self.load_file(
                os.path.join(
                    self.basiclib_dir,
                    'builtins.aki'
                )
            )

            # Next, load the platform library
            self.load_file(
                os.path.join(
                    self.basiclib_dir,
                    'platform',
                    os.name,
                    'platformlib.aki'
                )
            )

            # Finally, load the non-platform dependent basiclib
            self.load_file(
                os.path.join(
                    self.basiclib_dir,
                    self.basiclib_file
                )
            )

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
        self.codegen = LLVMCodeGenerator(vartypes=self.vartypes)

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
        anon_vartype = options.get('anon_vartype', self.vartypes.DEFAULT_TYPE)

        for ast in Parser(anon_vartype=anon_vartype, vartypes=self.vartypes).parse_generator(codestr):
            yield self._eval_ast(ast, **options)

    def eval_all(self, codestr, options=dict()):
        '''
        Evaluate multiple top-level statements and return the final value.
        '''
        for _ in self.eval_generator(codestr, options):
            pass
        return _.value

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

    def _add_platform_lib(self, module):
        import os
        import importlib
        builtins = importlib.import_module(f'core.stdlib.{os.name}')
        builtins.platform_lib(self, module)

    def _set_return_type(self, f_type):
        if not hasattr(f_type, 'c_type'):
            r_type = c_void_p
        else:
            r_type = f_type.c_type
        return r_type

    # TODO: Break out the compilation phase so it can be performed on its own

    def _eval_ast(self,
                  ast,
                  optimize=True,
                  llvmdump=False,
                  noexec=False,
                  parseonly=False,
                  verbose=False,
                  anon_vartype=None,
                  # return_type=c_int32,
                  return_type=None,
                  core_vartypes=None,
                  vartypes=None):
        """ 
        Evaluate a single top level expression given in ast form

            optimize: activate optimizations

            llvmdump: generated IR and assembly code will be dumped prior to execution.

            noexec: the code will be generated but not executed. Yields non-optimized IR.

            parseonly: the code will only be parsed. Yields an AST dump.

            verbose: yields a quadruplet tuple: result, AST, non-optimized IR, optimized IR

        """

        if not anon_vartype:
            anon_vartype = self.vartypes.DEFAULT_TYPE

        start_time = perf_counter()

        rawIR = None
        optIR = None
        if parseonly:
            return Result(ast.dump(), ast, rawIR, optIR, None)

        # Generate code
        self.codegen.generate_code(ast)
        if noexec or verbose:
            rawIR = lastIR(self.codegen.module)

        if noexec:
            return Result(rawIR, ast, rawIR, optIR, None)

        if llvmdump:
            dump(
                str(self.codegen.module),
                f'{paths["dump_dir"]}\\__dump__unoptimized.ll')

        # If we're evaluating a definition or extern declaration, don't do
        # anything else. If we're evaluating an anonymous wrapper for a toplevel
        # expression, JIT-compile the module and run the function to get its
        # result.

        def_or_extern = not ((isinstance(ast, Function) and ast.is_anonymous())
                             # or (isinstance(ast,Uni))
                             )

        if def_or_extern and not verbose:
            return Result(None, ast, rawIR, optIR, None)

        if ast.is_anonymous():
            return_value = self.codegen.module.globals[ast.proto.name].return_value

        # TODO: we should be able to make the base var type propagate this
        # tried that, doesn't work yet

        return_type = self._set_return_type(return_value.type)

        # Convert LLVM IR into in-memory representation and verify the code
        llvmmod = llvm.parse_assembly(str(self.codegen.module))
        llvmmod.verify()

        # Optimize the module
        if optimize:
            from core.compiler import optimize
            llvmmod, _ = optimize(llvmmod, self.codegen.pragmas)

            if llvmdump:
                dump(
                    str(llvmmod), f'{paths["dump_dir"]}\\__dump__optimized.ll')

        if verbose:
            optIR = lastIR(llvmmod, -2)
            if def_or_extern:
                return Result(None, ast, rawIR, optIR, None)

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

            end_time = perf_counter()

            fptr = CFUNCTYPE(return_type)(ee.get_function_address(name))

            try:
                result = fptr()
            except OSError as e:
                print(colored(f'OS error: {e}', 'red'))
                return Result(-1, ast, rawIR, optIR, None)

            if return_value.type.v_id == "ptr_str":
                result = cast(
                    result+self.codegen.vartypes._byte_width, POINTER(c_char_p))
                result = cast(result.contents, POINTER(c_char_p))
                result = f'"{str(string_at(result),"utf8")}"'

            return Result(result, ast, rawIR, optIR, end_time-start_time)

    def eval_and_return(self, node):
        '''
        Evaluate a single node and return its value.
        '''

        # Codegen a function that obtains the computed result
        # for this constant
        self.codegen.generate_code(
            Function.Anonymous(node.position, node)
        )

        # Extract the variable type of that function
        f_type = self.codegen.module.globals[
            Prototype.anon_name(Prototype)
        ].return_value.type

        r_type = self._set_return_type(f_type)

        # Run the function with the proper return type
        e = self._eval_ast(
            Function.Anonymous(node.position, node, vartype=f_type),
            return_type=r_type
        )

        return e
