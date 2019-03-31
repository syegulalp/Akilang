from llvmlite import ir, binding

import colorama

colorama.init()
CMD = colorama.Fore.YELLOW
REP = colorama.Fore.WHITE

RED = colorama.Fore.RED
XX = colorama.Fore.RESET

GRN = colorama.Fore.GREEN
MAG = colorama.Fore.MAGENTA


class Comment(ir.values.Value):
    def __init__(self, parent, text):
        self.text = text

    def __repr__(self):
        return f"; {self.text}"


ir.instructions.Comment = Comment


def comment(self, txt):
    self._insert(ir.instructions.Comment(self.block, txt))


ir.builder.IRBuilder.comment = comment

import ctypes
import os

from core.lex import AkiLexer
from core.parse import AkiParser
from core.codegen import AkiCodeGen
from core.compiler import AkiCompiler, ir

from core.astree import Function, Call, Prototype, VarType, ExpressionBlock, TopLevel
from core.error import AkiBaseErr
from core.error import ReloadException, QuitException
from core import constants

PROMPT = "A>"

USAGE = f"""From the {PROMPT} prompt, type Aki code or enter special commands
preceded by a dot sign:

    {CMD}.about|ab{REP}     : About this program.
    {CMD}.compile|cp{REP}   : Compile current module to executable.
    {CMD}.dump|dp{REP}      : Dump current module to console.
    {CMD}.exit|quit|stop|q{REP}
                  : Stop and exit the program.
    {CMD}.export|ex <filename>{REP}
                  : Dump current module to file in LLVM assembler format.
                  : Uses output.ll in current directory as default.
    {CMD}.help|.?|.{REP}    : Show this message.
    {CMD}.rerun|..{REP}     : Reload the Python code and restart the REPL. 
    {CMD}.rl[c|r]{REP}      : Reset the interpreting engine and reload the last .aki
                    file loaded in the REPL. Add c to run .cp afterwards.
                    Add r to run main() afterwards.
    {CMD}.reset|~{REP}      : Reset the interpreting engine.
    {CMD}.run|r{REP}        : Run the main() function (if present) in the current
                    module.
    {CMD}.test|t{REP}       : Run unit tests.
    {CMD}.version|ver|v{REP}
                  : Print version information.
    {CMD}.<file>.{REP}      : Load <file>.aki from the src directory.
                    For instance, .l. will load the Conway's Life demo.

These commands are also available directly from the command line, for example: 

    {CMD}aki 2 + 3
    aki test
    aki .myfile.aki{REP}
    
On the command line, the initial dot sign can be replaced with a double dash: 
    
    {CMD}aki --test
    aki --myfile.aki{REP}
"""


class JIT:
    lexer = AkiLexer()
    parser = AkiParser()

    def __init__(self):
        self.anon_counter = 0        
        self.reset()        

    def reset(self):
        self.compiler = AkiCompiler()
        self.module = ir.Module()
        self.codegen = AkiCodeGen(self.module)

def cp(string):
    print(f"{REP}{string}")


class Repl:

    import sys

    VERSION = f"""Python :{sys.version}
LLVM   :{".".join((str(n) for n in binding.llvm_version_info))}
pyaki  :{constants.VERSION}"""

    def __init__(self):
        self.main_cpl = JIT()
        self.repl_cpl = JIT()

    def run_tests(self, *a):
        print (f'{REP}', end='')
        import unittest

        tests = unittest.defaultTestLoader.discover("tests", "*.py")
        unittest.TextTestRunner().run(tests)

    def load_file(self, file_to_load):
        self.main_cpl.reset()        

        filepath = f"examples/{file_to_load}.aki"

        try:
            with open(filepath) as file:
                text = file.read()
                file_size = os.fstat(file.fileno()).st_size
                cp(f"Read {file_size} bytes from {CMD}{filepath}{REP}")
        except FileNotFoundError:
            cp(f"File not found: {CMD}{filepath}{REP}")
            return

        tokens = self.main_cpl.lexer.tokenize(text)
        ast = self.main_cpl.parser.parse(tokens, text)

        self.main_cpl.codegen.text = text
        self.main_cpl.codegen.eval(ast)
        self.main_cpl.compiler.compile_module(self.main_cpl.module, "main")

    def quit(self, *a):
        print(XX)
        raise QuitException

    def reload(self, *a):
        raise ReloadException

    def run(self):
        cp(
            f"{GRN}{constants.WELCOME}\n{REP}Type {CMD}.help{REP} or a command to be interpreted"
        )
        while True:
            try:
                print(f"{REP}{PROMPT}{CMD}", end="")
                text = input()
                self.cmd(text)
            except AkiBaseErr as e:
                print(e)
            except EOFError:
                break

    def help(self, *a):
        cp(f"\n{USAGE}")

    def cmd(self, text):
        if not text:
            return
        if text[0] == ".":
            if len(text) == 1:
                self.help()
                return
            if text[-1] == ".":
                if len(text) == 2:
                    return self.reload()
                text = text[1:-1]
                self.load_file(text)
                return
            command = text[1:]
        else:
            print(f"{REP}", end="")
            for _ in self.interactive(text):
                print(_)
            return

        cmd_func = self.cmds.get(command, None)

        if cmd_func is None:
            cp(f'Unrecognized command "{CMD}{command}{REP}"')
            return

        return cmd_func(self, text)

    def interactive(self, text, immediate_mode=False):
        # Immediate mode processes everything in the repl compiler.
        # Nothing is retained.

        if immediate_mode:
            main = self.repl_cpl
            main_file = None
            repl_file = None
        else:
            main = self.main_cpl
            main_file = "main"
            repl_file = "repl"

        self.repl_cpl.reset()

        # Tokenize input

        tokens = self.repl_cpl.lexer.tokenize(text)
        ast = self.repl_cpl.parser.parse(tokens, text)

        # Iterate through tokens

        self.repl_cpl.codegen.text = text
        main.codegen.text = text

        for _ in ast:

            # Toplevel commands are compiled in directly

            if isinstance(_, TopLevel):
                main.codegen.eval([_])
                main.compiler.compile_module(main.module, main_file)
                continue

            # Other commands are wrapped in an anonymous
            # function and executed

            self.repl_cpl.anon_counter += 1

            call_name = f".ANONYMOUS.{self.repl_cpl.anon_counter}"
            proto = Prototype(_.p, call_name, (), VarType(_.p, None))
            func = Function(_.p, proto, ExpressionBlock(_.p, [_]))

            if not immediate_mode:
                self.repl_cpl.codegen.other_modules.append(self.main_cpl.codegen)

            try:
                self.repl_cpl.codegen.eval([func])
            except AkiBaseErr as e:
                del self.repl_cpl.module.globals[call_name]
                raise e

            if not immediate_mode:
                if self.main_cpl.compiler.mod_ref:                    
                    self.repl_cpl.compiler.backing_mod.link_in(
                        self.main_cpl.compiler.mod_ref, True
                    )

            self.repl_cpl.compiler.compile_module(self.repl_cpl.module, repl_file)

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
            yield res



    def about(self, *a):
        print(f"\n{GRN}{constants.ABOUT}\n\n{self.VERSION}\n")

    def not_implemented(self, *a):
        cp(f"{RED}Not implemented yet")

    def version(self, *a):
        print(f"\n{GRN}{self.VERSION}\n")

    def load_test(self, *a):
        self.load_file("1")

    cmds = {
        "t": run_tests,
        "l": load_test,
        "q": quit,
        ".": reload,
        "ab": about,
        "about": about,
        "compile": not_implemented,
        "cp": not_implemented,
        "dump": not_implemented,
        "dp": not_implemented,
        "exit": quit,
        "quit": quit,
        "stop": quit,
        "q": quit,
        "export": not_implemented,
        "ex": not_implemented,
        "help": help,
        "?": help,
        "rerun": not_implemented,
        "rl": not_implemented,
        "rlc": not_implemented,
        "rlr": not_implemented,
        "reset": not_implemented,
        "~": not_implemented,
        "run": not_implemented,
        "r": not_implemented,
        "test": run_tests,
        "version": version,
        "ver": version,
        "v": version,
    }

