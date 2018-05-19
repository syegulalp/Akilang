#OUTPUT_DIR = 'output'

import subprocess
import pathlib

from core.repl import paths
from core.constants import compiler_path


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

    import llvmlite.binding as llvm

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    llvm_module = llvm.parse_assembly(str(module))

    llvm_module, pm = optimize(llvm_module)

    import os, errno
    try:
        os.makedirs(paths["output_dir"])
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    with open(f'{paths["output_dir"]}{os.sep}{filename}.opt.llvm',
              'w') as file:
        file.write(str(llvm_module))

    tm2 = llvm.Target.from_default_triple()
    tm = tm2.create_target_machine(opt=3, codemodel='large')
    tm.add_analysis_passes(pm)

    with llvm.create_mcjit_compiler(llvm_module, tm) as ee:
        ee.finalize_object()
        with open(f'{paths["output_dir"]}{os.sep}{filename}.obj',
                  'wb') as file:
            file.write(tm.emit_object(llvm_module))

    # TODO: ditch using batch file, use subprocess exclusively

    try:
        subprocess.run(
            f'{paths["compiler_dir"]}{os.sep}{compiler_path} {paths["output_dir"]}\\{filename}',
            shell=True,
            check=True)
    except subprocess.CalledProcessError as e:
        print(f'Build failed with the following error:\n{e}')
    else:
        print(
            f'Build successful for {paths["output_dir"]}{os.sep}{filename}.exe'
        )
