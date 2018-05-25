def config():
    import configparser
    cfg = configparser.ConfigParser()
    while 1:
        try:
            with open('config.ini') as file:
                cfg.read_file(file)
        except FileNotFoundError:
            defaults = '''[paths]
lib_dir=lib
basiclib=basiclib.aki
source_dir=src
compiler_dir=compile
output_dir=output
dump_dir=.
editor=notepad.exe
'''
            with open('config.ini', 'w') as file:
                file.write(defaults)
        else:
            break

        # TODO: we should also create the empty directories
        # as needed here

    return cfg


cfg = config()
paths = cfg['paths']

import copy
import colorama
import llvmlite
import sys
from importlib import reload
from termcolor import colored, cprint
colorama.init()

from core import errors, vartypes, lexer, operators, parsing, ast_module, codegen, codexec, compiler
from core.constants import PRODUCT, VERSION, COPYRIGHT


class ReloadException(Exception):
    pass


EXAMPLES = [
    'def add(a, b) a + b',
    'add(1, 2)',
    'add(add(1,2), add(3,4))',
    'max(1,2)',
    'max(max(1,2), max(3,4))',
    'factorial(5)',
    #'def i32 alphabet(i32 a i32 b) for x = 64 + a, x < 64 + b +1,x  + 1 in putchar(x) ',
    # 'alphabet(1.,26.)-65.'
]

PROMPT = 'A>'

USAGE = f"""From the {PROMPT} prompt, type Aki code or enter special commands
preceded by a dot sign:

    .about|.ab    : About this program.
    .compile|.cp  : Compile current module to executable.
    .dump|.dp     : Dump current module to console.
    .dumpfile|.df : Dump current module to .ll file.
    .example      : Run some code examples.
    .exit|quit|stop|q
                  : Stop and exit the program.
    .export <filename>
                  : Dump current module to file in LLVM assembler format.
    .list|.l      : List all available language functions and operators.
    .help|.       : Show this message.
    .options|opts|op
                  : Print the actual options settings.
    .rerun|..     : Reload the python code and restart the REPL from scratch. 
    .rl[c|r]      : Reset the interpreting engine and reload the last .aki
                    file loaded in the REPL. Add c to run .cp afterwards.
                    Add r to run main() afterwards.
    .reset|.~     : Reset the interpreting engine.
    .run|.r       : Run the main() function (if present) in the current
                    module.
    .test|tests   : Run unit tests.
    .version|ver  : Print version information.
    .<file>       : Run the given file .aki in the src directory.
    .<option>     : Toggle the given option on/off.

These commands are also available directly from the command line, for example: 

    aki 2 + 3
    aki test
    aki .myfile.aki
    
On the command line, the initial dot sign can be replaced with a double dash: 
    
    aki --test
    aki --myfile.aki
    """

ABOUT = f'''
{PRODUCT} v.{VERSION}
© {COPYRIGHT} Serdar Yegulalp

Based on code created by:
- Frédéric Guérin (https://github.com/frederickjeanguerin/pykaleidoscope)
- Eli Bendersky (https://github.com/eliben/pykaleidoscope)
'''

history = []

last_file = None


def errprint(msg):
    cprint(msg, 'red', file=sys.stderr)


def print_eval(ak, code, options=dict()):
    """Evaluate the given code with evaluator engine ak using the given options.
    Print the evaluation results. """
    results = ak.eval_generator(code, options)
    try:
        for result in results:
            if not result.value is None:
                cprint(result.value, 'green')
            else:
                history.append(result.ast)

            if options.get('verbose'):
                print('\n>>> Raw IR >>>\n')
                cprint(result.rawIR, 'green')
                print('\n>>> Optimized IR >>>\n')
                cprint(result.optIR, 'magenta')
                print()
    except lexer.AkiSyntaxError as err:
        errprint(f'Syntax error: {err}')
        ak.reset(history)
    except parsing.ParseError as err:
        errprint(f'Parse error: {err}')
        ak.reset(history)
    except codegen.CodegenError as err:
        errprint(f'Eval error: {err}')
        ak.reset(history)
    except RuntimeError as err:
        errprint(f'LLVM error: {err}')
    except Exception as err:
        errprint(str(type(err)) + ' : ' + str(err))
        print(' Aborting.')
        raise


def run_tests():
    import unittest
    tests = unittest.defaultTestLoader.discover("tests", "*.py")
    unittest.TextTestRunner().run(tests)


def print_funlist(funlist):
    for func in funlist:
        description = "{:>6} {:<20} ({})".format(
            'extern' if func.is_declaration else '   def',
            func.public_name,
            ', '.join((f'{arg.name}:{arg.type.descr()}' for arg in func.args))
        )
        cprint(description, 'yellow')


def print_functions(ak):
    # Operators
    print(colored('\nBuiltin operators:', 'green'),
          *operators.builtin_operators())

    # User vs extern functions
    sorted_functions = sorted(
        ak.codegen.module.functions, key=lambda fun: fun.name)
    user_functions = filter(lambda f: not f.is_declaration and getattr(
        f, '_local_visibility', True), sorted_functions)
    extern_functions = filter(lambda f: f.is_declaration and getattr(
        f, '_local_visibility', True) is not False, sorted_functions)

    cprint('\nUser defined functions and operators:\n', 'green')
    print_funlist(user_functions)

    cprint('\nExtern functions:\n', 'green')
    print_funlist(extern_functions)


def run_repl_command(ak, command, options):
    if command in options:
        options[command] = not options[command]
        print(command, '=', options[command])
    elif command in ('example', 'examples'):
        run_examples(ak, EXAMPLES, options)
    elif command in ('dump', 'dp'):
        print(ak.codegen.module)
    elif command in ('dumpfile', 'df'):
        output = str(ak.codegen.module)
        filename = f'{paths["dump_dir"]}\\dump.ll'
        with open(filename, 'w') as file:
            file.write(output)
        print(f'{len(output)} bytes written to {filename}')
    elif command in ('compile', 'cp'):
        compiler.compile(ak.codegen.module, 'output')
    elif command in ('export',) or command.startswith('export '):
        try:
            filename = command.split(' ')[1]
            if '.' not in filename:
                filename += ".ll"
        except IndexError:
            import os
            filename = f'output{os.sep}output.ll'

        with open(filename, 'w') as file:
            output = str(ak.codegen.module)
            file.write(output)
        print(f'{len(output)} bytes written to {filename}')
    elif command in ('list', 'l'):
        print_functions(ak)
    elif command in ('help', '?', ''):
        print(USAGE)
    elif command in ('about', 'ab'):
        print(ABOUT)
    elif command in ('options', 'opts', 'op'):
        print(options)
    elif command in ('quit', 'exit', 'stop', 'q'):
        sys.exit()
    elif command in ('rerun', '.'):
        raise ReloadException()
    elif command in ('reset', '~'):
        reload(parsing)
        ak.reset()
        global history
        history = []
    elif command in ('run', 'r'):
        print_eval(ak, 'main()', options)
    elif command in ('rl', 'rlc', 'rlr'):
        if last_file is None:
            errprint('No previous command to reload')
        else:
            reload(parsing)
            ak.reset()
            load_command(last_file, ak, options)
        if command == 'rlr':
            print_eval(ak, 'main()', options)
        elif command == 'rlc':
            compiler.compile(ak.codegen.module, 'output')
    elif command in ('test', 'tests'):
        run_tests()
    elif command in ('version', 'ver'):
        print('Python :', sys.version)
        print('LLVM   :', '.'.join(
            (str(n) for n in llvmlite.binding.llvm_version_info))
        )
        print('pyaki  :', VERSION)
    elif command:
        load_command(command, ak, options)


def load_command(command, ak, options):
        # Here the command should be a filename, open it and run its content

    if command[-1] == '.':
        command += 'aki'
    try:
        with open(f'{paths["source_dir"]}\\{command}', encoding='utf8') as file:
            f = file.read()
            print(f'{command} read in ({len(f)} bytes)')
            global last_file
            last_file = command
            print_eval(ak, f, options)

    except FileNotFoundError:
        errprint("File or command not found: " + command)


def run_command(ak, command, options):
    print(colorama.Fore.YELLOW, end='')
    if not command:
        pass
    elif command in ['help', 'quit', 'exit', 'stop', 'test']:
        run_repl_command(ak, command, options)
    elif command[0] == '.':
        run_repl_command(ak, command[1:], options)
    else:
        # command is an akilang code snippet so run it
        print_eval(ak, command, options)
    print(colorama.Style.RESET_ALL, end='')


def run_examples(ak, commands, options):
    for command in commands:
        print(PROMPT, command)
        print_eval(ak, command, options)


def run(*a, optimize=True, llvmdump=False, noexec=False, parseonly=False, verbose=False):
    options = locals()
    options.pop('a')
    k = codexec.AkilangEvaluator(
        #f'{paths["lib_dir"]}\\{paths["basiclib"]}.aki')
        f'{paths["lib_dir"]}',
        f'{paths["basiclib"]}',
        )

    # If some arguments passed in, run that command then exit
    if len(sys.argv) >= 2:
        command = ' '.join(sys.argv[1:]).replace('--', '.')
        run_command(k, command, options)
    else:
        # Enter a REPL loop
        cprint(f'{PRODUCT} v.{VERSION}', 'yellow')
        cprint('Type help or a command to be interpreted', 'green')
        command = ""
        while not command in ['exit', 'quit']:
            run_command(k, command, options)
            print(PROMPT, end="")
            command = input().strip()

# to add:
# .ed <filename>: Create/open an .aki file (do not specify extension) in
#                 the src directory, using the system default editor for
#                 .aki files. The resulting file can then be loaded and
#                 run by way of the .rl command.
# .launch|.ll   : Compile current module to executable and launch it.
