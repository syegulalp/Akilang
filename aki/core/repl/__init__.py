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

from core.lex import AkiLexer
from core.parse import AkiParser
from core.codegen import AkiCodeGen
from core.compiler import AkiCompiler, ir

from core.astree import Function, Call, Prototype, VarType, ExpressionBlock, TopLevel
from core.error import AkiBaseErr
from core.error import ReloadException, QuitException


class Repl:
    def __init__(self):

        self.lexer = AkiLexer()
        self.parser = AkiParser()

        gc.freeze()

        self.module = ir.Module()
        self.codegen = AkiCodeGen(self.module)
        self.compiler = AkiCompiler()

        self.anon_counter = 0

    def run_tests(self, *a):
        import unittest

        tests = unittest.defaultTestLoader.discover("tests", "*.py")
        unittest.TextTestRunner().run(tests)

    def load_file(self, *a):
        self.module = ir.Module()
        self.codegen = AkiCodeGen(self.module)
        self.compiler = AkiCompiler()

        with open("examples/in.aki") as file:
            text = file.read()
        tokens = self.lexer.tokenize(text)
        ast = self.parser.parse(tokens, text)
        self.codegen.text = text
        self.codegen.eval(ast)
        self.compiler.compile_module(self.module)

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

        # Tokenize input

        tokens = self.lexer.tokenize(text)
        ast = self.parser.parse(tokens, text)

        # Iterate through tokens

        self.codegen.text = text

        for _ in ast:

            # Toplevel commands are compiled in directly

            if isinstance(_, TopLevel):

                self.codegen.eval([_])
                self.compiler.compile_module(self.module)
                continue

            # Other commands are wrapped in an anonymous
            # function and executed

            else:

                # Generate anonymous function

                self.anon_counter += 1

                call_name = f".ANONYMOUS_{self.anon_counter}"
                proto = Prototype(_.p, call_name, (), VarType(_.p, None))
                func = Function(_.p, proto, ExpressionBlock(_.p, [_]))

                try:
                    self.codegen.eval([func])
                except AkiBaseErr as e:
                    del self.module.globals[call_name]
                    raise e

                self.compiler.compile_module(self.module)

                # Retrieve a pointer to the function

                func_ptr = self.compiler.get_addr(call_name)

                return_val = self.module.globals[
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

                # Delete the anonymous function
                # ideally we should do this by having the anon
                # in another module, link in the target function,
                # and then drop the anon module entirely

                del self.module.globals[call_name]

    cmds = {"t": run_tests, "l": load_file, "q": quit, ".": reload}
