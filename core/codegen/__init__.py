from core.ast_module import Prototype, Function, Uni, Class, Decorator, Call
from core.vartypes import VarTypes 
from core.errors import CodegenError
from core.mangling import mangle_args

import llvmlite.ir as ir
import llvmlite.binding as llvm

from core.codegen.builtins import Builtins as Builtins_Class
from core.codegen.toplevel import Toplevel
from core.codegen.vars import Vars
from core.codegen.ops import Ops
from core.codegen.controlflow import ControlFlow

class LLVMCodeGenerator(Builtins_Class, Toplevel, Vars, Ops, ControlFlow):
    def __init__(self):
        '''
        Initialize the code generator.
        This creates a new LLVM module into which code is generated. The
        generate_code() method can be called multiple times. It adds the code
        generated for this node into the module, and returns the IR value for
        the node.
        At any time, the current LLVM module being constructed can be obtained
        from the module attribute.
        '''
        # Current module.
        self.module = ir.Module()

        # Current IR builder.
        self.builder = None

        # Manages a symbol table while a function is being codegen'd.
        # Maps var names to ir.Value.
        self.func_symtab = {}

        # Decorator stack for whatever function is currently in context.
        self.func_decorators = []

        # Holds class definitions for codegen.
        self.class_symtab = {}

        # Holds a stack of loop exits.
        # Used to track where to break out of a loop.
        self.loop_exit = []

        # Holds functions that have optional arguments.
        # This allows them to be looked up efficiently.
        self.opt_args_funcs = {}

        # Variable graphs for tracing memory allocation.
        # Functions that "give" allocated memory by way of a variable.
        self.gives_alloc = set()

        # Flag for unsafe operations.
        self.allow_unsafe = False

        # Initialize target data for the module.
        self.target_data = llvm.create_target_data(self.module.data_layout)

        # Set up pointer size and u_size vartype for current hardware.
        self.pointer_size = (ir.PointerType(VarTypes.u8).get_abi_size(
            self.target_data))

        self.pointer_bitwidth = self.pointer_size * 8

        from core.vartypes import UnsignedInt
        VarTypes['u_size'] = UnsignedInt(self.pointer_bitwidth)
        VarTypes['u_mem'] = UnsignedInt(self.pointer_size)

        import ctypes
        VarTypes.u_size.c_type = ctypes.c_voidp
        VarTypes.u_mem.c_type = ctypes.c_uint8

        # XXX: this causes ALL instances of .u_size
        # in the environment instance
        # to be set to the platform width!
        # we may not want to have this behavior
        # what we may want to do is have a master instance of the target data
        # which we use to create the types,
        # and then refer to that unless it's explicitly overloaded?

        self.noneobj = ir.GlobalVariable(
            self.module,
            VarTypes['None'],
            '.none.'
        )
        self.noneobj.initializer = ir.Constant(VarTypes['None'],(0,))
        self.noneobj.global_constant = True
        self.noneobj.unnamed_addr = True
        self.noneobj.storage_class = 'private'

    def _int(self, pyval):
        '''
        Returns a constant for Python int value.
        Used for gep, so it returns a value that is the bitwidth
        of the pointer size for the needed architecture.
        '''
        return ir.Constant(VarTypes.u_size, int(pyval))

    def _i32(self, pyval):
        '''
        Returns a constant for 32-bit int value.
        Also used for gep where a 32-bit value is required.
        '''
        return ir.Constant(VarTypes.u32, int(pyval))

    def generate_code(self, node):
        assert isinstance(node, (Prototype, Function, Uni, Class, Decorator))
        return self._codegen(node, False)

    def _extract_operand(self, val):
        '''
        Extracts the first operand for a load or alloca statement.
        Used to examine the actual variable underlying such.
        This is used mainly when determining if a variable being traced
        through a function has its heap_alloc attribute set,
        to further determine if it needs to be disposed automatically
        when it goes out of scope.
        '''
        if hasattr(val, 'operands') and val.operands:
            return val.operands[0]
        else:
            return val

    def _isize(self):
        '''
        Returns a constant of the pointer size for the currently configured architecture.
        The size is obtained from the LLVMCodeGenerator object, and is set when
        that object is instantiated. By default it's the pointer size for the current
        hardware, but you will be able to override it later.
        '''
        return ir.Constant(VarTypes.u_size, self.pointer_size)

    def _obj_size_type(self, obj):
        return obj.get_abi_size(self.target_data)

    def _obj_size(self, obj):
        return self._obj_size_type(obj.type)

    def _alloca(self, name, alloca_type=None, size=None, current_block=False):
        '''
        Create an alloca, by default in the entry BB of the current function.
        Set current_block=True to use the current block.
        '''

        assert alloca_type is not None
        if current_block:
            alloca = self.builder.alloca(alloca_type, size=size, name=name)
        else:
            with self.builder.goto_entry_block():
                alloca = self.builder.alloca(alloca_type, size=size, name=name)
        return alloca

    def _varaddr(self, node, report=True):
        '''
        Retrieve the address of a variable indicated by a Variable AST object.
        '''
        if report:
            name = node.name
        else:
            name = node
        v = self.func_symtab.get(name)
        if v is None:
            v = self.module.globals.get(name)
        if v is None:
            if not report:
                return None
            raise CodegenError(f"Undefined variable: {node.name}",
                               node.position)
        return v
        
    def _codegen(self, node, check_for_type=True):
        '''
        Node visitor. Dispatches upon node type.
        For AST node of class Foo, calls self._codegen_Foo. Each visitor is
        expected to return a llvmlite.ir.Value.
        '''

        method = '_codegen_' + node.__class__.__name__
        result = getattr(self, method)(node)

        if check_for_type and not hasattr(result, 'type'):
            raise CodegenError(
                f'Expression does not return a value along all code paths, or expression returns an untyped value',
                node.position)

        return result

    def _codegen_dunder_methods(self, node):
        call = self._codegen_Call(
            Call(node.position, node.name,
                 node.args
                 ),
            obj_method=True
        )
        return call

    def _codegen_methodcall(self, node, lhs, rhs):
        func = self.module.globals.get(
            f'binary.{node.op}{mangle_args((lhs.type,rhs.type))}')
        if func is None:
            raise NotImplementedError
        return self.builder.call(func, [lhs, rhs], 'userbinop')



    def _codegen_autodispose(self, item_list, to_check):
        for _,v in item_list:
            if v is to_check:
                continue
            
            # if this is an input argument,
            # and it's still being tracked (e.g., not given away),
            # and the variable in question has not been deleted
            # manually at any time, 
            # ...?
            
            if v.input_arg is not None:
                pass

            if v.tracked:
                ref = self.builder.load(v)
                sig = v.type.pointee.pointee.signature()
                self.builder.call(
                    self.module.globals.get(sig+'__del__'),
                    [ref],
                    f'{_}.delete'
                    )                    



