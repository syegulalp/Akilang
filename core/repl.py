from core.constants import PRODUCT, VERSION, COPYRIGHT, CONFIG_INI_DEFAULTS, ABOUT

import colorama
import llvmlite
import sys
from importlib import reload
from termcolor import colored, cprint
colorama.init()

from time import perf_counter

def config():
    import configparser
    cfg = configparser.ConfigParser()
    while 1:
        try:
            with open('config.ini') as file:
                cfg.read_file(file)
        except FileNotFoundError:
            cprint(f'"config.ini" file recreated', 'red')
            defaults = CONFIG_INI_DEFAULTS
            with open('config.ini', 'w') as file:
                file.write(defaults)
        else:
            break

        # TODO: we should also create the empty directories
        # as needed here

    return cfg


cfg = config()
paths = cfg['paths']

from core import errors, vartypes, lexer, operators, parsing, ast_module, codegen, codexec, compiler

from core.errors import ReloadException

PROMPT = 'A>'

USAGE = f"""From the {PROMPT} prompt, type Aki code or enter special commands
preceded by a dot sign:

    .about|.ab    : About this program.
    .compile|.cp  : Compile current module to executable.
    .dump|.dp     : Dump current module to console.
    .dumpfile|.df : Dump current module to .ll file.
    .exit|quit|stop|q
                  : Stop and exit the program.
    .export|ex <filename>
                  : Dump current module to file in LLVM assembler format.
                  : Uses dump.ll in current directory as default.
    .help|.       : Show this message.
    .rerun|..     : Reload the Python code and restart the REPL. 
    .rl[c|r]      : Reset the interpreting engine and reload the last .aki
                    file loaded in the REPL. Add c to run .cp afterwards.
                    Add r to run main() afterwards.
    .reset|.~     : Reset the interpreting engine.
    .run|.r       : Run the main() function (if present) in the current
                    module.
    .test|tests   : Run unit tests.
    .version|ver  : Print version information.
    .<file>.      : Load <file>.aki from the src directory.
                    For instance, .l. will load the Conway's Life demo.

These commands are also available directly from the command line, for example: 

    aki 2 + 3
    aki test
    aki .myfile.aki
    
On the command line, the initial dot sign can be replaced with a double dash: 
    
    aki --test
    aki --myfile.aki
    """

def errprint(msg):
    cprint(msg, 'red', file=sys.stderr)


class Repl():    

    def __init__(self):
        self.commands = {
            'test': self.run_tests,
            'reset': self.reset,
            '~': self.reset,
            'rerun': self.reload_all,
            '.': self.reload_all,
            'r': self.run_program,
            'run': self.run_program,
            'help': self.print_usage,
            '?': self.print_usage,
            '': self.print_usage,
            'dump': self.dump_module,
            'dp': self.dump_module,
            'dumpfile': self.dump_module_to_file,
            'df': self.dump_module_to_file,
            'compile': self.compile_module,
            'cp': self.compile_module,
            'export': self.export_module,
            'ex': self.export_module,
            'about': self.about,
            'ab': self.about,
            'quit': self.quit,
            'exit': self.quit,
            'stop': self.quit,
            'q': self.quit,
            'rl': self.reload_module,
            'rlc': self.reload_module,
            'rlr': self.reload_module,
            'version': self.version,
            'ver':self.version,
            'v': self.version

        }
        
        self.history = []

    def reset(self, *a):
        reload(parsing)
        self.executor.reset()
        print ("Interpreting engine reset")
        self.history = []
        print ("Command history cleared")
        self.last_file = None

    def version(self, *a):
        print('Python :', sys.version)
        print('LLVM   :', '.'.join(
            (str(n) for n in llvmlite.binding.llvm_version_info))
        )
        print('pyaki  :', VERSION)
    
    def reload_module(self, command):
        if self.last_file is None:
            errprint('No previous command to reload')
            return
        
        reload(parsing)
        self.executor.reset()
        self.load_command(self.last_file)

        if command == 'rlr':
            self.run_program(command)
        elif command == 'rlc':
            self.compile_module(command)
    
    def reload_all(self, *a):
        raise ReloadException()

    def run_tests(self, *a):
        import unittest
        tests = unittest.defaultTestLoader.discover("tests", "*.py")
        unittest.TextTestRunner().run(tests)

    def run_program(self, *a):
        self.print_eval('main()')
    
    def print_usage(self, *a):
        print(USAGE)
    
    def about(self, *a):
        print(ABOUT)
    
    def quit(self, *a):
        sys.exit()

    def dump_module(self, *a):
        print(self.executor.codegen.module)

    def compile_module(self, *a):
        compiler.compile(self.executor.codegen, 'output')

    def export_module(self, command):
        try:
            filename = command.split(' ')[1]
            if '.' not in filename:
                filename += ".ll"
        except IndexError:
            import os
            filename = f'output{os.sep}output.ll'

        with open(filename, 'w') as file:
            output = str(self.executor.codegen.module)
            file.write(output)
        
        print(f'{len(output)} bytes written to {filename}')

    def dump_module_to_file(self, *a):
        output = str(self.executor.codegen.module)
        filename = f'{paths["dump_dir"]}\\dump.ll'
        with open(filename, 'w') as file:
            file.write(output)
        print(f'{len(output)} bytes written to {filename}')

    def load_command(self, command):
        if command[-1] == '.':
            command+='aki'
        try:
            with open(f'{paths["source_dir"]}\\{command}', encoding='utf8') as file:
                f = file.read()
                print(f'{command} read in ({len(f)} bytes)')
                self.last_file = command
                start_time=perf_counter()
                self.print_eval(f)
                finish_time=perf_counter()-start_time
                print (f"Compile time: {finish_time:.3f}s")

        except (FileNotFoundError, OSError):
            errprint("File or command not found: " + command)

    def print_eval(self, code):
        '''
        Evaluate the given code with evaluator engine
        using the instance options.
        Print the evaluation results.
        '''
        results = self.executor.eval_generator(code)
        try:
            for result in results:
                if not result.value is None:
                    cprint(result.value, 'green')
                else:
                    self.history.append(result.ast)
                if self.options.get('verbose'):
                    print('\n>>> Raw IR >>>\n')
                    cprint(result.rawIR, 'green')
                    print('\n>>> Optimized IR >>>\n')
                    cprint(result.optIR, 'magenta')
                    print()
        except lexer.AkiSyntaxError as err:
            errprint(f'Syntax error: {err}')
            self.executor.reset(history)
        except parsing.ParseError as err:
            errprint(f'Parse error: {err}')
            self.executor.reset(self.history)
        except codegen.CodegenError as err:
            errprint(f'Eval error: {err}')
            self.executor.reset(self.history)
        except RuntimeError as err:
            errprint(f'LLVM error: {err}')
        except Exception as err:
            errprint(str(type(err)) + ' : ' + str(err))
            print('Aborting.')
            #self.executor.reset()
            raise err

    def run_command(self, command):        
        print(colorama.Fore.YELLOW, end='')
        
        if not command:
            pass
        elif command[0] == '.':
            # run dot command
            self.run_repl_command(command[1:])
        else:
            # command is an akilang code snippet so run it
            self.print_eval(command)

        print(colorama.Style.RESET_ALL, end='')

    def run_repl_command(self, command):
        
        try:
            self.commands[command](command)
        except KeyError:
            self.load_command(command)

    def run(self, *a):
        self.core_vartypes = vartypes.generate_vartypes()        
        self.options = locals()
        self.options.pop('a')
        
        self.executor = codexec.AkilangEvaluator(
            f'{paths["lib_dir"]}',
            f'{paths["basiclib"]}',
            vartypes=self.core_vartypes
        )

        if len(sys.argv) >= 2:
            command = ' '.join(sys.argv[1:]).replace('--', '.')
            self.run_command(command)
        else:
            # Enter a REPL loop
            cprint(f'{PRODUCT} v.{VERSION}', 'yellow')
            cprint('Type help or a command to be interpreted', 'green')
            command = ""
            while not command in ['exit', 'quit']:
                self.run_command(command)
                cprint(PROMPT, 'white', end='')
                command = input().strip()

