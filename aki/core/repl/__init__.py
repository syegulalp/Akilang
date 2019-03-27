from llvmlite import ir


class Comment(ir.values.Value):
    def __init__(self, parent, text):
        self.text = text

    def __repr__(self):
        return f"; {self.text}"


ir.instructions.Comment = Comment


def comment(self, txt):
    self._insert(ir.instructions.Comment(self.block, txt))


ir.builder.IRBuilder.comment = comment

import gc
import ctypes
import os

from core.lex import AkiLexer
from core.parse import AkiParser
from core.codegen import AkiCodeGen
from core.compiler import AkiCompiler, ir

from core.astree import Function, Call, Prototype, VarType, ExpressionBlock, TopLevel
from core.error import AkiBaseErr
from core.error import ReloadException, QuitException

class JIT():
    def __init__(self):
        self.lexer = AkiLexer()
        self.parser = AkiParser()        
        self.anon_counter = 0
        self.reset()        
    
    def reset(self):
        self.module = ir.Module()
        self.codegen = AkiCodeGen(self.module)
        self.compiler = AkiCompiler()

class Repl:
    def __init__(self):
        gc.freeze()
        
        self.main_cpl = JIT()
        self.repl_cpl = JIT()        

    def run_tests(self, *a):
        import unittest

        tests = unittest.defaultTestLoader.discover("tests", "*.py")
        unittest.TextTestRunner().run(tests)

    def load_file(self, *a):
        self.main_cpl.reset()

        with open("examples/in.aki") as file:
            text = file.read()
            file_size = os.fstat(file.fileno()).st_size
        print(f"Read {file_size} bytes")
        
        tokens = self.main_cpl.lexer.tokenize(text)
        ast = self.main_cpl.parser.parse(tokens, text)
        self.main_cpl.codegen.text = text
        self.main_cpl.codegen.eval(ast)
        self.main_cpl.compiler.compile_module(
            self.main_cpl.module, 'main')

    def quit(self, *a):
        raise QuitException

    def reload(self, *a):
        raise ReloadException

    def run(self):
        while True:
            try:
                text = input("A> ")
                self.cmd(text)
            except AkiBaseErr as e:
                print(e)
            except EOFError:
                break

    def cmd(self, text):
        if not text:
            return

        if text[0] == ".":
            command = text[1:]
        else:
            self.interactive(text)
            return

        cmd_func = self.cmds.get(command, None)

        if cmd_func is None:
            print(f'Unrecognized command "{command}"')
            return

        return cmd_func(self, text)

    def interactive(self, text):

        self.repl_cpl.reset()

        # Tokenize input

        tokens = self.repl_cpl.lexer.tokenize(text)
        ast = self.repl_cpl.parser.parse(tokens, text)

        # Iterate through tokens

        self.repl_cpl.codegen.text = text

        for _ in ast:

            # Toplevel commands are compiled in directly

            if isinstance(_, TopLevel):

                self.repl_cpl.codegen.eval([_])
                self.repl_cpl.compiler.compile_module(self.repl_cpl.module)
                continue

            # Other commands are wrapped in an anonymous
            # function and executed

            else:

                # Generate anonymous function

                self.repl_cpl.anon_counter += 1

                call_name = f".ANONYMOUS_{self.repl_cpl.anon_counter}"
                proto = Prototype(_.p, call_name, (), VarType(_.p, None))
                func = Function(_.p, proto, ExpressionBlock(_.p, [_]))

                self.repl_cpl.codegen.other_modules.append(self.main_cpl.codegen)

                try:
                    self.repl_cpl.codegen.eval([func])
                except AkiBaseErr as e:
                    del self.repl_cpl.module.globals[call_name]
                    raise e

                if self.main_cpl.compiler.mod_ref:
                    self.repl_cpl.compiler.backing_mod.link_in(self.main_cpl.compiler.mod_ref, True)
                
                self.repl_cpl.compiler.compile_module(self.repl_cpl.module, 'repl')
                
                # Retrieve a pointer to the function
                func_ptr = self.repl_cpl.compiler.get_addr(call_name)

                return_val = self.repl_cpl.module.globals[
                    call_name
                ].return_value.aki.return_type.aki_type.c()

                # Get the function signature
                # We're not using this right now but it might
                # come in handy later if we need to pass
                # parameters to the anon func for whatever reason.

                # func_signature = [
                #     _.aki.vartype.aki_type.c() for _ in module.globals[call_name].args
                # ]

                # Generate a result

                cfunc = ctypes.CFUNCTYPE(return_val, *[])(func_ptr)
                res = cfunc()
                print(res)



    cmds = {"t": run_tests, "l": load_file, "q": quit, ".": reload}
