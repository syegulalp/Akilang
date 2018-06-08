#OUTPUT_DIR = 'output'

import subprocess
import pathlib

from core.repl import paths


def optimize(llvm_module):
    import llvmlite.binding as llvm

    pmb = llvm.create_pass_manager_builder()
    pmb.opt_level = 3
    pmb.loop_vectorize = True
    pmb.slp_vectorize = True
    pm = llvm.create_module_pass_manager()
    pmb.populate(pm)
    pm.run(llvm_module)

    return llvm_module, pm


def compile(module, filename):

    print('Parsing source.')

    import llvmlite.binding as llvm

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    llvm_module = llvm.parse_assembly(str(module))

    llvm_module, pm = optimize(llvm_module)

    import os
    import errno
    try:
        os.makedirs(paths["output_dir"])
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    with open(f'{paths["output_dir"]}{os.sep}{filename}.opt.llvm',
              'w') as file:
        file.write(str(llvm_module))

    print('Creating object file.')

    tm2 = llvm.Target.from_default_triple()
    tm = tm2.create_target_machine(opt=3, codemodel='large')
    tm.add_analysis_passes(pm)

    with llvm.create_mcjit_compiler(llvm_module, tm) as ee:
        ee.finalize_object()
        output_file = tm.emit_object(llvm_module)
        with open(
            f'{paths["output_dir"]}{os.sep}{filename}.obj',
                'wb') as file:
            file.write(output_file)

    print(f'{len(output_file)} bytes written.')
    print('Linking object file.')

    if os.name == 'nt':

        extension = 'exe'

        cmds = [
            r'call "C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64',
            f'link.exe {paths["output_dir"]}{os.sep}{filename}.obj -defaultlib:ucrt msvcrt.lib user32.lib kernel32.lib legacy_stdio_definitions.lib /SUBSYSTEM:CONSOLE /MACHINE:X64 /OUT:{paths["output_dir"]}{os.sep}{filename}.{extension} /OPT:REF',
            r'EXIT /B %ERRORLEVEL%',
            ''
        ]

        shell = 'cmd.exe'

    else:
        raise Exception('Non-Win32 OSes not yet supported')

    try:
        p = subprocess.Popen(
            shell,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        for cmd in cmds:
            while True:
                p.poll()
                r = p.returncode
                if r is not None:
                    break
                t = p.stdout.readline().decode('utf-8')
                print(t.strip())
                if t in ('\r\n', '\n', '\r'):
                    break
            p.stdin.write(bytes(cmd+'\n', 'utf-8'))
            p.stdin.flush()

    except Exception as e:
        print(f'Build failed with the following error:\n{e}')

    else:
        print(
            f'Build successful for {paths["output_dir"]}{os.sep}{filename}.{extension}.'
        )

    p.terminate()
