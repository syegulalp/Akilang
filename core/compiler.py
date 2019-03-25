import llvmlite.binding as llvm
from llvmlite import ir
import datetime


class AkiCompiler:
    def __init__(self):
        """
        Create an ExecutionEngine suitable for JIT code generation on
        the host CPU.  The engine is reusable for an arbitrary number of
        modules.
        """

        llvm.initialize()
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()

        # Create a target machine representing the host
        self.target = llvm.Target.from_default_triple()
        self.target_machine = self.target.create_target_machine()

        # And an execution engine with an empty backing module
        backing_mod = llvm.parse_assembly("")
        self.engine = llvm.create_mcjit_compiler(backing_mod, self.target_machine)

        # Not used yet
        # engine.set_object_cache(export,None)

    def compile_ir(self, llvm_ir):
        """
        Compile the LLVM IR string with the given engine.
        The compiled module object is returned.
        """

        # Create a LLVM module object from the IR
        mod = llvm.parse_assembly(llvm_ir)
        mod.verify()

        # Now add the module and make sure it is ready for execution
        self.engine.add_module(mod)
        self.engine.finalize_object()
        self.engine.run_static_constructors()
        return mod

    def compile_bc(self, bc):
        """
        Compile the LLVM bitcode with the given engine.
        The compiled module object is returned.
        """

        mod = llvm.parse_bitcode(bc)
        mod.verify()

        # Now add the module and make sure it is ready for execution
        self.engine.add_module(mod)
        self.engine.finalize_object()
        self.engine.run_static_constructors()
        return mod

    def compile_module(self, module):
        """
        JIT-compiles the module for immediate execution.
        """

        llvm_ir = str(module)

        # Write IR to file for debugging
        with open(r"output//module.llvm", "w") as file:
            file.write(f"; File written at {datetime.datetime.now()}\n")
            file.write(llvm_ir)

        # Compiler IR to assembly
        mod = self.compile_ir(llvm_ir)

        # Write assembly to file
        with open(r"output//module.llvmbc", "wb") as file:
            file.write(mod.as_bitcode())

        return mod

    def get_addr(self, func_name="main"):
        # Obtain module entry point
        func_ptr = self.engine.get_function_address(func_name)
        return func_ptr
