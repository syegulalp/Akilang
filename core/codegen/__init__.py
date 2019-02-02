from core.ast_module import (
    Prototype,
    Function,
    Uni,
    Class,
    Decorator,
    Call,
    Pragma,
    Number,
)
from core.vartypes import generate_vartypes
from core.errors import CodegenError, SubError
from core.mangling import mangle_args

import llvmlite.ir as ir
import llvmlite.binding as llvm

from core.codegen.builtins import Builtins as Builtins_Class
from core.codegen.builtins_boxes import Builtins_boxes
from core.codegen.toplevel import Toplevel
from core.codegen.vars import Vars
from core.codegen.ops import Ops
from core.codegen.controlflow import ControlFlow

# pylint: disable=E1101


class NullBuilder:
    def __getattribute__(self, name):
        raise SubError(f"Operation cannot be performed outside of a function context")


class LLVMCodeGenerator(
    Builtins_Class, Builtins_boxes, Toplevel, Vars, Ops, ControlFlow
):
    def __init__(self, vartypes=None, module_name=None, context=None, force=False):
        """
        Initialize the code generator.
        This creates a new LLVM module into which code is generated. The
        generate_code() method can be called multiple times. It adds the code
        generated for this node into the module, and returns the IR value for
        the node.
        At any time, the current LLVM module being constructed can be obtained
        from the module attribute.
        """
        
        if force:
            context = ir.context.Context()
            self.module = ir.Module(module_name, context=context)
            vartypes = generate_vartypes(self.module, force=True)
        else:
            self.module = ir.Module(module_name)

        # Current IR builder.
        self.nullbuilder = NullBuilder()
        self.builder = self.nullbuilder

        # Manages a symbol table while a function is being codegen'd.
        # Maps var names to ir.Value.
        self.func_symtab = {}

        # Holds objects that have been deleted in a function
        self.deleted_symtab = {}

        # Allocations that need tracking.
        # self.allocations = {}
        self.alloc_stack = []

        # Decorator stack for whatever function is currently in context.
        self.func_decorators = []

        # Holds class definitions for codegen.
        self.class_symtab = {}

        # Holds a stack of tuples:
        # (loop exit block, loop continue block)
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

        # Context for current try/except block (if any)
        self.try_except = []

        # Pragmas for this module
        self.pragmas = {}

        # Last codegenned instruction
        self.previous = None
        self.last_inline = None

        if vartypes is None:
            vartypes = generate_vartypes(self.module)
        self.vartypes = vartypes

        # Counter for constants in a module
        # (to prevent name collisions)
        self._const_counter = 0

        # Evaluator instance for codegenning
        # compile-time constants
        self.evaluator = None

        self.suppress_warnings = True

    def init_evaluator(self):
        if self.evaluator is None:
            from core import codexec

            self.evaluator = codexec.AkilangEvaluator(True, vartypes=self.vartypes)
        else:
            self.evaluator.reset()
        return self.evaluator

    def const_counter(self):
        self._const_counter += 1
        return self._const_counter

    def _int(self, pyval):
        """
        Returns a constant for Python int value.
        Used for gep, so it returns a value that is the bitwidth
        of the pointer size for the needed architecture.
        """
        return ir.Constant(self.vartypes.u_size, int(pyval))

    def _i32(self, pyval):
        """
        Returns a constant for 32-bit int value.
        Also used for gep where a 32-bit value is required.
        """
        return ir.Constant(self.vartypes.u32, int(pyval))

    def generate_code(self, node):
        assert isinstance(node, (Prototype, Function, Uni, Class, Decorator, Pragma))
        return self._codegen(node, False)

    def _extract_operand(self, val):
        """
        Extracts the first operand for a load or alloca statement.
        Used to examine the actual variable underlying such.
        This is used mainly when determining if a variable being traced
        through a function has its heap_alloc attribute set,
        to further determine if it needs to be disposed automatically
        when it goes out of scope.
        """
        if hasattr(val, "operands") and val.operands:
            return val.operands[0]
        else:
            return val

    def _get_var(self, node, lhs):
        """
        Retrieves variable, if any, from a load op.
        Used mainly for += and -= ops.
        """
        if isinstance(lhs, ir.Constant):
            raise CodegenError(r"Can't assign value to literal", node.position)
        return self._extract_operand(lhs)

    def _isize(self):
        """
        Returns a constant of the pointer size for the currently configured architecture.
        The size is obtained from the LLVMCodeGenerator object, and is set when
        that object is instantiated. By default it's the pointer size for the current
        hardware, but you will be able to override it later.
        """
        return ir.Constant(self.varTypes.u_size, self.pointer_size)

    def _obj_size_type(self, obj):
        return obj.get_abi_size(self.vartypes._target_data)

    def _obj_size(self, obj):
        return self._obj_size_type(obj.type)

    def _set_tracking(self, node, do_not_allocate=True, heap_alloc=True, tracked=True):
        if heap_alloc is not None:
            node.heap_alloc = heap_alloc
        if do_not_allocate is not None:
            node.do_not_allocate = do_not_allocate
        if tracked is not None:
            node.tracked = tracked

    def _copy_tracking(self, lhs, rhs):
        lhs.heap_alloc = rhs.heap_alloc
        lhs.input_arg = rhs.input_arg
        lhs.tracked = rhs.tracked

        if lhs.heap_alloc:
            lhs.tracked = True

    def _alloca(
        self,
        name,
        alloca_type=None,
        size=None,
        current_block=False,
        malloc=False,
        node=None,
    ):
        """
        Create an alloca, by default in the entry BB of the current function.
        Set current_block=True to use the current block.
        """

        assert alloca_type is not None

        # print (alloca_type)
        # mem_alloc_size = alloca_type.get_abi_size(self.vartypes._target_data)
        # mem_alloc = self._codegen_Call(
        #     Call(node.position, 'c_alloc',
        #          [Number(node.position, mem_alloc_size, self.vartypes.u_size)]))
        # print (mem_alloc)

        if malloc:

            pass

            # Placeholder for when we use this to perform heap
            # as well as stack allocations
            # When this happens, we call platform allocator,
            # turn on tracking,
            # then return a properly typed pointer from the malloc

        else:

            def make_alloc():
                return self.builder.alloca(alloca_type, size=size, name=name)

        if current_block:
            return make_alloc()
        else:
            with self.builder.goto_block(self.func_varblock):
                return make_alloc()

    def _varaddr(self, node, report=True):
        """
        Retrieve the address of a variable indicated by a Variable AST object.
        """
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
            v=self.deleted_symtab.get(name)
            if v:
                raise CodegenError(f'Variable "{node.name}" previously deleted at {v.deleted_at} and is inaccessible from this position', node.position)
            raise CodegenError(f'Undefined variable "{node.name}"', node.position)
        return v

    def _codegen(self, node, check_for_type=True):
        """
        Node visitor. Dispatches upon node type.
        For AST node of class Foo, calls self._codegen_Foo. Each visitor is
        expected to return a llvmlite.ir.Value.
        """

        method = f"_codegen_{node.__class__.__name__}"
        try:
            result = getattr(self, method)(node)
        except SubError as e:
            raise CodegenError(str(e), node.position)

        if check_for_type and not hasattr(result, "type"):
            raise CodegenError(
                f"Expression does not return a value along all code paths, or expression returns an untyped value",
                node.position,
            )

        self.previous = result

        return result

    def _dunder_method(self, node):
        call = self._codegen_Call(
            Call(node.position, node.name, node.args), obj_method=True
        )
        return call

    def _methodcall(self, node, lhs, rhs):
        func = self.module.globals.get(
            f"binary.{node.op}{mangle_args((lhs.type,rhs.type))}"
        )
        if func is None:
            raise NotImplementedError
        return self.builder.call(func, [lhs, rhs], "userbinop")

    def _autodispose(self, item_list, to_check, node=None):
        for _, var_to_dispose in item_list:
            if var_to_dispose is to_check:
                continue            
            if var_to_dispose.tracked:
                if not var_to_dispose.type.pointee.is_obj_ptr():
                    continue
                # self._decr_refcount(var_to_dispose, node)                
                # self._free_obj(var_to_dispose, node)
                # self._call_del_method(var_to_dispose)


    def _call_del_method(self, var_to_dispose, node=None):
        ref = self.builder.load(var_to_dispose)

        v_target = var_to_dispose.type.pointee.pointee
        sig = v_target.del_signature()

        if v_target.del_as_ptr:
            ref = self.builder.bitcast(ref, self.vartypes.u_mem.as_pointer())

        # TODO: merge this with the existing
        # dunder-method call mechanism?

        del_name = self.module.globals.get(sig + mangle_args([ref.type]))

        # TODO: symtab should contain the position
        # for the first creation of a class object
        # so we can indicate errors like this precisely

        if del_name is None:
            raise CodegenError(
                f'No "__del__" method found for "{v_target.signature()}"', node.position
            )

        self.builder.call(del_name, [ref], f"{var_to_dispose.name}.delete")

    def _incr_refcount(self, var_ref, node):

        # Refcounts are not incremented on untracked objects
        if not var_ref.tracked:
            return
        
        # Get the underlying allocation for the variable
        alloc = self.builder.load(var_ref)

        # Bitcast the object to a bare header
        f2 = self.builder.bitcast(alloc, self.vartypes.header.as_pointer())

        # Call incr on header
        f3 = self._codegen(
            Call(node.position, ".obj..__incr__", [f2], self.vartypes.i32)
        )

    def _decr_refcount(self, var_ref, node, load=True):
        print ("Load:", load)
        # Refcounts are not incremented on untracked objects
        if not var_ref.tracked:
            return
            
        # Get the underlying allocation for the variable
        # (default operation)

        if load:                
            alloc = self.builder.load(var_ref)
            
            v1 = self.builder.alloca(var_ref.type)
            v2 = self.builder.store(var_ref, v1)
            # print (v1)

            fa = self.builder.ptrtoint(v1, self.vartypes.u_size)
            print (fa)
            fb = self.builder.inttoptr(fa, self.vartypes.u_mem.as_pointer())
            f4 = fb
        else:
            alloc = var_ref
            f4 = self.builder.bitcast(var_ref, self.vartypes.u_mem.as_pointer())


        # get addr of alloc
        
        print ("var ref:", var_ref)
        print ("var_ref type:", var_ref.type)
        print ("alloc type:", alloc.type)
        print ("f4:", f4)
        print ('----')

        f2 = self.builder.bitcast(alloc, self.vartypes.header.as_pointer())

        # Call decr on header
        f3 = self._codegen(
            Call(node.position, ".obj..__decr__", [f4, f2], self.vartypes.i32)
        )

        f5 = self._codegen(
            Call(node.position, ".obj.._free", [f4, f2], self.vartypes.i32)
        )

    def _free_obj(self, var_ref, node):
        #return
        #print ("Free:", var_ref, var_ref.tracked)
        
        if not var_ref.tracked:
            #print ("Not tracked")
            return
        
        #print (var_ref.type)

        alloc = self.builder.load(var_ref)

        # Bitcast the pointer to the object to raw memory
        #f2 = self.builder.bitcast(var_ref, self.vartypes.u_mem.as_pointer())
        f3 = self.builder.bitcast(alloc, self.vartypes.header.as_pointer())

        # Call free on header
        self._codegen(
            Call(node.position, ".obj.__del__", [f3], self.vartypes.i32)
        )