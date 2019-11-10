import llvmlite.binding as llvm
from llvmlite import ir
import datetime

llvm.initialize()
llvm.initialize_native_target()
llvm.initialize_native_asmprinter()

import os


class AkiCompiler:
    def __init__(self):
        """
        Create execution engine.
        """

        # Create a target machine representing the host
        self.target = llvm.Target.from_default_triple()
        self.target_machine = self.target.create_target_machine()

        # Prepare the engine with an empty module
        self.backing_mod = llvm.parse_assembly("")
        self.engine = llvm.create_mcjit_compiler(self.backing_mod, self.target_machine)
        self.mod_ref = None

        # Not used yet
        # self.engine.set_object_cache(export,None)

    def compile_ir(self, llvm_ir):
        """
        Compile a module from an LLVM IR string.
        """
        mod = llvm.parse_assembly(llvm_ir)
        return self.finalize_compilation(mod)

    def compile_bc(self, bc):
        """
        Compile a module from LLVM bitcode.
        """
        mod = llvm.parse_bitcode(bc)
        return self.finalize_compilation(mod)

    def finalize_compilation(self, mod):
        mod.verify()
        self.engine.add_module(mod)
        self.engine.finalize_object()
        self.engine.run_static_constructors()
        self.mod_ref = mod
        return mod

    def compile_module(self, module, filename="output"):
        """
        JIT-compiles the module for immediate execution.
        """

        llvm_ir = str(module)

        # Write IR to file for debugging

        if filename:
            if not os.path.exists("output"):
                os.mkdir("output")
            with open(os.path.join("output", f"{filename}.akil"), "w") as file:
                file.write(f"; File written at {datetime.datetime.now()}\n")
                file.write(llvm_ir)

        mod = self.compile_ir(llvm_ir)

        # Write bitcode

        if filename:
            with open(os.path.join("output", f"{filename}.akib"), "wb") as file:
                file.write(mod.as_bitcode())

    def get_addr(self, func_name="main"):
        # Obtain module entry point
        func_ptr = self.engine.get_function_address(func_name)
        return func_ptr
