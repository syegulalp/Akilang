#OUTPUT_DIR = 'output'

import subprocess
import pathlib

from core.repl import paths


def optimize(llvm_module, metas={}):
    import llvmlite.binding as llvm

    pmb = llvm.create_pass_manager_builder()

    pmb.loop_vectorize = metas.get('loop_vectorize', True)
    pmb.slp_vectorize = metas.get('slp_vectorize', True)

    pmb.opt_level = metas.get('opt_level', 3)
    pmb.size_level = metas.get('size_level', 0)

    pmb.disable_unroll_loops = not (metas.get('unroll_loops', True))

    pm = llvm.create_module_pass_manager()
    pmb.populate(pm)
    pm.run(llvm_module)

    return llvm_module, pm


def compile(codegen, filename):
    module = codegen.module

    print('Parsing source.')

    import llvmlite.binding as llvm

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    llvm_module = llvm.parse_assembly(str(module))

    llvm_module, pm = optimize(llvm_module, codegen.metas)

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
            r"pushd .",
            r'call "C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64',
            r'popd',
            f'link.exe {paths["output_dir"]}{os.sep}{filename}.obj -defaultlib:ucrt msvcrt.lib user32.lib kernel32.lib legacy_stdio_definitions.lib /SUBSYSTEM:CONSOLE /MACHINE:X64 /OUT:{paths["output_dir"]}{os.sep}{filename}.{extension} /OPT:REF',
            r'exit %errorlevel%',
        ]

        shell_cmd = [os.environ['COMSPEC']]

    else:
        raise Exception('Non-Win32 OSes not yet supported')

    try:
        p = subprocess.Popen(
            shell_cmd,
            shell=False,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        for cmd in cmds:
            for line in p.stdout:
                ln = line.decode('utf-8').strip()
                if len(ln) == 0:
                    break
                print(ln)

            p.poll()
            r = p.returncode
            if r is not None:
                break

            print()

            p.stdin.write(bytes(cmd+'\n', 'utf-8'))
            p.stdin.flush()

        errs = ''.join([n.decode('utf-8') for n in p.stderr.readlines()])
        if len(errs):
            raise Exception(errs)

    except Exception as e:
        print(f'Build failed with the following error:\n{e}')

    else:
        print(
            f'Build successful for {paths["output_dir"]}{os.sep}{filename}.{extension}.'
        )

    finally:
        p.terminate()
