import warnings
import llvmlite.ir as ir
import llvmlite.binding as llvm

from core.ast_module import (
    Binary, Variable, Prototype, Function, Uni, Class, Decorator,
    Array, If, Number, ArrayAccessor, Call, Var,
    _ANONYMOUS, Const
)
from core.vartypes import SignedInt, DEFAULT_TYPE, VarTypes, Str, Array as _Array, CustomClass
from core.errors import MessageError, ParseError, CodegenError, CodegenWarning
from core.parsing import Builtins, Dunders, decorator_collisions
from core.operators import BUILTIN_UNARY_OP
from core.mangling import mangle_call, mangle_args, mangle_types, mangle_funcname, mangle_optional_args


class LLVMCodeGenerator(object):
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

        self.target_data = llvm.create_target_data(self.module.data_layout)

        # Set up pointer size and u_size vartype for current hardware.
        self.pointer_size = (ir.PointerType(VarTypes.u8).get_abi_size(
            self.target_data))

        self.pointer_bitwidth = self.pointer_size * 8

        from core.vartypes import UnsignedInt
        VarTypes['u_size'] = UnsignedInt(self.pointer_bitwidth)

        import ctypes
        VarTypes.u_size.c_type = ctypes.c_voidp
        # XXX: this causes ALL instances of .u_size
        # in the environment instance
        # to be set to the platform width!
        # we may not want to have this behavior

    def _int(self, pyval):
        '''
        Returns a constant for Python int value.
        Used for gep, so it returns a value that is the bitwidth
        of the pointer size for the needed architecture.
        '''
        return ir.Constant(VarTypes.u_size, int(pyval))

    def _i32(self, pyval):
        '''
        Returns a constant for Python int value.
        Used for gep, so it returns a value that is the bitwidth
        of the pointer size for the needed architecture.
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
            to_check = val.operands[0]
        else:
            to_check = val
        return to_check


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
        Create an alloca in the entry BB of the current function.
        '''

        assert alloca_type is not None
        if current_block:
            alloca = self.builder.alloca(alloca_type, size=size, name=name)
        else:
            with self.builder.goto_entry_block():
                alloca = self.builder.alloca(alloca_type, size=size, name=name)
        return alloca

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

    def _codegen_NoneType(self, node):
        pass

    def _codegen_Number(self, node):
        num = ir.Constant(node.vartype, node.val)
        return num

    def _codegen_VariableType(self, node):
        return node.vartype

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

    def _codegen_Return(self, node):
        '''
        Generates a return from within a function, and 
        sets the `self.func_returncalled` flag
        to notify that a return has been triggered.
        '''

        retval = self._codegen(node.val)
        if self.func_returntype is None:
            raise CodegenError(f'Unknown return declaration error', 
                node.position)

        if retval.type != self.func_returntype:
            raise CodegenError(
                f'In function "{self.func_incontext.public_name}", expected return type "{self.func_returntype.describe()}" but got "{retval.type.describe()}" instead',
                node.val.position)

        self.builder.store(retval, self.func_returnarg)
        self.builder.branch(self.func_returnblock)
        self.func_returncalled = True

        # Check for the presence of a returned object
        # that requires memory tracing
        # if so, add it to the set of functions that returns a trackable object

        to_check = self._extract_operand(retval)

        if to_check.tracked:
            self.gives_alloc.add(self.func_returnblock.parent)
            self.func_returnblock.parent.returns.append(to_check)

    def _codegen_ArrayElement(self, node, array):
        '''
        Returns a pointer to the requested element of an array.
        '''
        accessor = [
            self._i32(0),
            self._i32(1),
        ] + [self._codegen(n) for n in node.elements]

        # FIXME: This is intended to trap wrongly sized array accessors
        # but we should find a more elegant way to do it in the parsing
        # phase if possible

        try:
            ptr = self.builder.gep(array, accessor, True, f'{array.name}')
        except (AttributeError, IndexError):
            raise CodegenError(
                f'Invalid array accessor for "{array.name}" (maybe wrong number of dimensions?)',
                node.position)

        return ptr

    def _codegen_Decorator(self, node):
        '''
        Set the decorator stack and generate the code tagged by the decorator.
        '''

        self.func_decorators.append(node.name)
        for n in node.body:
            _ = self._codegen(n, False)
        self.func_decorators.pop()
        return _

    def _codegen_Variable(self, node, noload=False):

        current_node = node
        previous_node = None

        # At the bottom of each iteration of the loop,
        # we should return a DIRECT pointer to an object

        while True:

            if previous_node is None and isinstance(current_node, Variable):
                if isinstance(getattr(current_node, 'child', None), (Call,)):
                    previous_node = current_node
                    current_node = current_node.child
                    continue

                latest = self._varaddr(current_node)
                current_load = not latest.type.is_obj_ptr()

            elif isinstance(current_node, ArrayAccessor):
                # eventually this will be coded as a call
                # to __index__ method of the element in question

                if latest.type.is_obj_ptr():
                    # objects are passed by reference
                    array_element = latest
                else:
                    if not isinstance(latest, ir.instructions.LoadInstr):
                        # if the array object is not yet loaded,
                        # then we need to allocate and store ptr
                        array_element = self.builder.alloca(latest.type)
                        self.builder.store(latest, array_element)
                    else:
                        # otherwise, just point to the existing allocation
                        array_element = self._varaddr(previous_node)    

                latest = self._codegen_ArrayElement(
                    current_node, array_element)
                current_load = not latest.type.is_obj_ptr()

            elif isinstance(current_node, Call):
                # eventually, when we have function pointers,
                # we'll need to have a pattern here similar to how
                # we handle ArrayAccessors above
                # e.g., encoded as __call__

                latest = self._codegen_Call(current_node)
                current_load = False
                # TODO: why is a call the exception?

            elif isinstance(current_node, Variable):
                try:
                    oo = latest.type.pointee
                except AttributeError:
                    raise CodegenError(f'Not a pointer or object', current_node.position)

                _latest_vid = oo.v_id
                _cls = self.class_symtab[_latest_vid]
                _pos = _cls.v_types[current_node.name]['pos']

                # for some reason we can't use i64 gep here

                index = [
                    self._i32(0),
                    self._i32(_pos)
                ]

                latest = self.builder.gep(
                    latest, index, True,
                    previous_node.name + '.' + current_node.name)

                current_load = not latest.type.is_obj_ptr()

            # pathological case
            else:
                raise CodegenError(f'Unknown variable instance', current_node.position)

            child = getattr(current_node, 'child', None)
            if child is None:
                break

            if current_load:
                latest = self.builder.load(latest, node.name+'.accessor')

            previous_node = current_node
            current_node = child

        if noload is True:
            return latest

        if current_load:
            return self.builder.load(latest, node.name)
        else:
            return latest

    def _codegen_Class(self, node):
        self.class_symtab[node.name] = node.vartype

    def _codegen_Assignment(self, lhs, rhs):
        if not isinstance(lhs, Variable):
            raise CodegenError(
                f'Left-hand side of expression is not a variable and cannot be assigned a value at runtime',
                lhs.position
            )

        ptr = self._codegen_Variable(lhs, noload=True)
        if getattr(ptr, 'global_constant', None):
            raise CodegenError(
                f'Universal constant "{lhs.name}" cannot be reassigned',
                lhs.position)

        is_func = ptr.type.is_func()

        if is_func:
            rhs_name = mangle_call(rhs.name, ptr.type.pointee.pointee.args)
            value = self.module.globals.get(rhs_name)
            if 'varfunc' not in value.decorators:
                raise CodegenError(
                    f'Function "{rhs.name}" must be decorated with "@varfunc" to allow variable assignments',
                    rhs.position
                )

        else:
            value = self._codegen(rhs)

        if ptr.type.pointee != value.type:
            if getattr(lhs, 'accessor', None):
                error_string = f'Cannot assign value of type "{value.type.describe()}" to element of array "{ptr.pointer.name}" of type "{ptr.type.pointee.describe()}"'
            else:
                error_string = f'Cannot assign value of type "{value.type.describe()}" to variable "{ptr.name}" of type "{ptr.type.pointee.describe()}"',
            raise CodegenError(error_string, rhs.position)

        self.builder.store(value, ptr)

        return value

    def _codegen_String(self, node):
        return self._string_base(node.val)

    def _string_base(self, string, global_constant=True):
        '''
        Core function for code generation for strings.        
        This will also be called when we create strings dynamically
        in the course of a function, or statically during compilation.
        '''
        # only strings codegenned from source should be stored as LLVM globals
        module = self.module
        string_length = len(string.encode('utf8')) + 1
        type = ir.ArrayType(ir.IntType(8), string_length)

        str_name = f'.str.{len(module.globals)}'

        # Create the LLVM constant value for the underlying string data.

        str_const = ir.GlobalVariable(module, type, str_name + '.dat')
        str_const.storage_class = 'private'
        str_const.unnamed_addr = True
        str_const.global_constant = True

        str_const.initializer = ir.Constant(
            type,
            bytearray(string, 'utf8') + b'\x00')

        # Get pointer to first element in string's byte array
        # and bitcast it to a ptr i8.

        spt = str_const.gep([self._int(0)]).bitcast(VarTypes.u8.as_pointer())

        # Create the string object that points to the constant.

        str_val = ir.GlobalVariable(module, VarTypes.str, str_name)
        str_val.storage_class = 'private'
        str_val.unnamed_addr = True
        str_val.global_constant = True

        str_val.initializer = VarTypes.str(
            [ir.Constant(VarTypes.u32, string_length), spt])

        return str_val

    def _codegen_methodcall(self, node, lhs, rhs):
        func = self.module.globals.get(
            f'binary.{node.op}{mangle_args((lhs.type,rhs.type))}')
        if func is None:
            raise NotImplementedError
        return self.builder.call(func, [lhs, rhs], 'userbinop')

    def _codegen_Binary(self, node):
        # Assignment is handled specially because it doesn't follow the general
        # recipe of binary ops.

        if node.op == '=':
            return self._codegen_Assignment(node.lhs, node.rhs)

        lhs = self._codegen(node.lhs)
        rhs = self._codegen(node.rhs)

        if lhs.type != rhs.type:
            raise CodegenError(
                f'"{lhs.type.describe()}" ({node.lhs.name}) and "{rhs.type.describe()}" ({node.rhs.name}) are incompatible types for operation',
                node.position)
        else:
            vartype = lhs.type
            v_type = getattr(lhs.type, 'v_type', None)

        try:
            # For non-primitive types we need to look up the property

            if v_type is not None:
                if v_type == Str:
                    raise NotImplementedError

            # TODO: no overflow checking!
            # we have to add that when we have exceptions, etc.
            # with fcmp_ordered this is assuming we are strictly comparing
            # float to float in all cases.

            # Integer operations

            if isinstance(vartype, ir.IntType):

                if lhs.type.signed:
                    signed_op = self.builder.icmp_signed
                else:
                    signed_op = self.builder.icmp_unsigned

                if node.op == '+':
                    return self.builder.add(lhs, rhs, 'addop')
                elif node.op == '-':
                    return self.builder.sub(lhs, rhs, 'subop')
                elif node.op == '*':
                    return self.builder.mul(lhs, rhs, 'multop')
                elif node.op == '<':
                    x = signed_op('<', lhs, rhs, 'ltop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '>':
                    x = signed_op('>', lhs, rhs, 'gtop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '>=':
                    x = signed_op('>=', lhs, rhs, 'gteqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '<=':
                    x = signed_op('<=', lhs, rhs, 'lteqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '==':
                    x = signed_op('==', lhs, rhs, 'eqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '!=':
                    x = signed_op('!=', lhs, rhs, 'neqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '/':
                    if int(getattr(rhs, 'constant', 1)) == 0:
                        raise CodegenError('Integer division by zero', node.rhs.position)
                    return self.builder.sdiv(lhs, rhs, 'divop')
                elif node.op == 'and':
                    x = self.builder.and_(lhs, rhs, 'andop') # pylint: disable=E1111
                    x.type = VarTypes.bool
                    return x
                elif node.op == 'or':
                    x = self.builder.or_(lhs, rhs, 'orop') # pylint: disable=E1111
                    x.type = VarTypes.bool
                    return x
                else:
                    return self._codegen_methodcall(node, lhs, rhs)

            # floating-point operations

            elif isinstance(vartype, (ir.DoubleType, ir.FloatType)):

                if node.op == '+':
                    return self.builder.fadd(lhs, rhs, 'faddop')
                elif node.op == '-':
                    return self.builder.fsub(lhs, rhs, 'fsubop')
                elif node.op == '*':
                    return self.builder.fmul(lhs, rhs, 'fmultop')
                elif node.op == '/':
                    return self.builder.fdiv(lhs, rhs, 'fdivop')
                elif node.op == '<':
                    cmp = self.builder.fcmp_ordered('<', lhs, rhs, 'fltop')
                    return self.builder.uitofp(cmp, vartype, 'fltoptodouble')
                elif node.op == '>':
                    cmp = self.builder.fcmp_ordered('>', lhs, rhs, 'fgtop')
                    return self.builder.uitofp(cmp, vartype, 'flgoptodouble')
                elif node.op == '>=':
                    cmp = self.builder.fcmp_ordered('>=', lhs, rhs, 'fgeqop')
                    return self.builder.uitofp(cmp, vartype, 'fgeqopdouble')
                elif node.op == '<=':
                    cmp = self.builder.fcmp_ordered('<=', lhs, rhs, 'fleqop')
                    return self.builder.uitofp(cmp, vartype, 'fleqopdouble')
                elif node.op == '==':
                    x = self.builder.fcmp_ordered('==', lhs, rhs, 'feqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '!=':
                    x = self.builder.fcmp_ordered('!=', lhs, rhs, 'fneqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op in ('and', 'or'):
                    raise CodegenError(
                        'Operator not supported for "float" or "double" types',
                        node.lhs.position)
                else:
                    return self._codegen_methodcall(node, lhs, rhs)

            # Pointer equality

            elif isinstance(vartype, ir.PointerType):
                # TODO: use vartype.is_obj_ptr() to determine
                # if this is a complex object that needs to invoke
                # its __eq__ method, but this is fine for now
                signed_op = self.builder.icmp_unsigned
                if isinstance(rhs.type, ir.PointerType):
                    if node.op == '==':
                        x = signed_op('==', lhs, rhs, 'eqptrop')
                        x.type = VarTypes.bool
                        return x

            else:
                return self._codegen_methodcall(node, lhs, rhs)

        except NotImplementedError:
            raise CodegenError(
                f'Unknown binary operator {node.op} for {vartype}',
                node.position)

    def _codegen_Match(self, node):
        cond_item = self._codegen(node.cond_item)
        default = ir.Block(self.builder.function, 'defaultmatch')
        exit = ir.Block(self.builder.function, 'endmatch')
        switch_instr = self.builder.switch(cond_item, default)
        cases = []
        exprs = {}
        for value, expr, in node.match_list:
            val_codegen = self._codegen(value)
            if not isinstance(val_codegen, ir.values.Constant):
                raise CodegenError(
                    f'Match parameter must be a constant, not an expression',
                    value.position)
            if val_codegen.type != cond_item.type:
                raise CodegenError(
                    f'Type of match object ("{cond_item.type.describe()}") and match parameter ("{val_codegen.type.describe()}") must be consistent)',
                    value.position)
            if expr in exprs:
                switch_instr.add_case(val_codegen, exprs[expr])
            else:
                n = ir.Block(self.builder.function, 'match')
                switch_instr.add_case(val_codegen, n)
                exprs[expr] = n
                cases.append([n, expr])
        for block, expr in cases:
            self.builder.function.basic_blocks.append(block)
            self.builder.position_at_start(block)
            result = self._codegen(expr, False)
            if result:
                self.builder.branch(exit)
        self.builder.function.basic_blocks.append(default)
        self.builder.position_at_start(default)
        if node.default:
            self._codegen(node.default, False)
        self.builder.branch(exit)
        self.builder.function.basic_blocks.append(exit)
        self.builder.position_at_start(exit)
        return cond_item

    def _codegen_When(self, node):
        return self._codegen_If(node, True)

    def _codegen_If(self, node, codegen_when=False):
        # Emit comparison value

        cond_val = self._codegen(node.cond_expr)

        type = cond_val.type

        cond = ('!=', cond_val, ir.Constant(type, 0), 'notnull')

        if isinstance(type, (ir.FloatType, ir.DoubleType)):
            cmp = self.builder.fcmp_unordered(*cond)
        elif isinstance(type, SignedInt):
            cmp = self.builder.icmp_signed(*cond)
        else:
            cmp = self.builder.icmp_unsigned(*cond)

        # Create basic blocks to express the control flow
        then_bb = ir.Block(self.builder.function, 'then')
        else_bb = ir.Block(self.builder.function, 'else')
        merge_bb = ir.Block(self.builder.function, 'endif')

        # branch to either then_bb or else_bb depending on cmp
        # if no else, then go straight to merge
        if node.else_expr is None:
            self.builder.cbranch(cmp, then_bb, merge_bb)
        else:
            self.builder.cbranch(cmp, then_bb, else_bb)

        # Emit the 'then' part
        self.builder.function.basic_blocks.append(then_bb)
        self.builder.position_at_start(then_bb)

        self.breaks = False

        then_val = self._codegen(node.then_expr, False)
        if then_val:
            self.builder.branch(merge_bb)

        # Emission of then_val could have generated a new basic block
        # (and thus modified the current basic block).
        # To properly set up the PHI, remember which block the 'then' part ends in.
        then_bb = self.builder.block

        # Emit the 'else' part, if needed

        if node.else_expr is None:
            else_val = None
        else:
            self.builder.function.basic_blocks.append(else_bb)
            self.builder.position_at_start(else_bb)
            else_val = self._codegen(node.else_expr)
            if else_val:
                self.builder.branch(merge_bb)
            else_bb = self.builder.block

        # check for an early return,
        # prune unneeded phi operations

        self.builder.function.basic_blocks.append(merge_bb)
        self.builder.position_at_start(merge_bb)

        if then_val is None and else_val is None:
            # returns are present in each branch
            return
        elif not else_val:
            # return present in 1st branch only
            return then_val.type
        elif not then_val:
            # return present in 2nd branch only
            return else_val.type
        # otherwise no returns in any branch

        if codegen_when:
            return cond_val

        # make sure then/else are in agreement
        # so we're returning consistent types

        if then_val.type != else_val.type:
            raise CodegenError(
                f'"then/else" expression return types must be the same ("{then_val.type.describe()}" does not match "{else_val.type.describe()}"',
                node.position)

        phi = self.builder.phi(then_val.type, 'ifval')
        phi.add_incoming(then_val, then_bb)
        phi.add_incoming(else_val, else_bb)
        return phi

    def _codegen_Break(self, node):
        exit = self.loop_exit.pop()
        self.breaks = True
        self.builder.branch(exit)

    def _codegen_Loop(self, node):
        # Output this as:
        #   ...
        #   start = startexpr
        #   goto loopcond
        # loopcond:
        #   variable = phi [start, loopheader], [nextvariable, loopbody]
        #   step = stepexpr (or variable + 1)
        #   nextvariable = step
        #   endcond = endexpr
        #   br endcond, loopbody, loopafter
        # loopbody:
        #   bodyexpr
        #   jmp loopcond
        # loopafter:
        #   return variable

        # Define blocks
        loopcond_bb = ir.Block(self.builder.function, 'loopcond')
        loopbody_bb = ir.Block(self.builder.function, 'loopbody')
        loopafter_bb = ir.Block(self.builder.function, 'loopafter')

        # If this loop has no conditions, codegen it with a manual exit

        if node.start_expr is None:
            self.builder.branch(loopbody_bb)
            self.builder.function.basic_blocks.append(loopbody_bb)
            self.builder.position_at_start(loopbody_bb)
            self.loop_exit.append(loopafter_bb)
            self._codegen(node.body, False)
            self.builder.branch(loopbody_bb)
            self.builder.function.basic_blocks.append(loopafter_bb)
            self.builder.position_at_start(loopafter_bb)
            return

        # ###########
        # loop header
        #############

        var_addr = self._varaddr(node.start_expr.name, False)
        if var_addr is None:
            self._codegen_Var(Var(node.start_expr.position, [node.start_expr]))
            var_addr = self._varaddr(node.start_expr.name, False)
        else:
            self._codegen_Assignment(
                node.start_expr,
                node.start_expr.initializer
            )

        loop_ctr_type = var_addr.type.pointee

        # Jump to loop cond
        self.builder.branch(loopcond_bb)

        ###########
        # loop cond
        ###########

        self.builder.function.basic_blocks.append(loopcond_bb)
        self.builder.position_at_start(loopcond_bb)

        # Set the symbol table to to reach de local counting variable.
        # If it shadows an existing variable, save it before and restore it later.
        oldval = self.func_symtab.get(node.start_expr.name)
        self.func_symtab[node.start_expr.name] = var_addr

        # Compute the end condition
        endcond = self._codegen(node.end_expr)

        # TODO: this requires different comparison operators
        # based on the type of the loop object - int vs. float, chiefly
        # this is a pattern we may repeat too often

        cond = ('!=', endcond, ir.Constant(loop_ctr_type, 0), 'loopifcond')

        if isinstance(loop_ctr_type, (ir.FloatType, ir.DoubleType)):
            cmp = self.builder.fcmp_unordered(*cond)
        elif isinstance(loop_ctr_type, ir.IntType):
            if getattr(loop_ctr_type, 'v_signed', None):
                cmp = self.builder.icmp_signed(*cond)
            else:
                cmp = self.builder.icmp_unsigned(*cond)

        # Goto loop body if condition satisfied, otherwise, exit.
        self.builder.cbranch(cmp, loopbody_bb, loopafter_bb)

        ############
        # loop body
        ############

        self.builder.function.basic_blocks.append(loopbody_bb)
        self.builder.position_at_start(loopbody_bb)

        # Emit the body of the loop.
        # Note that we ignore the value computed by the body.
        self._codegen(node.body, False)

        # If the step is unknown, make it increment by 1
        if node.step_expr is None:
            node.step_expr = Binary(node.position, "+",
                                    Variable(node.position,
                                             node.start_expr.name),
                                    Number(None, 1, loop_ctr_type))

        # Evaluate the step and update the counter
        nextval = self._codegen(node.step_expr)
        self.builder.store(nextval, var_addr)

        # Goto loop cond
        self.builder.branch(loopcond_bb)

        #############
        # loop after
        #############

        # New code will be inserted into a new block
        self.builder.function.basic_blocks.append(loopafter_bb)
        self.builder.position_at_start(loopafter_bb)

        # Remove the loop variable from the symbol table;
        # if it shadowed an existing variable, restore that.
        if oldval is None:
            del self.func_symtab[node.start_expr.name]
        else:
            self.func_symtab[node.start_expr.name] = oldval

        # The 'loop' expression returns the last value of the counter
        return self.builder.load(var_addr)

    def _codegen_While(self, node):
        # This is a modified version of a For.

        # Define blocks
        loopcond_bb = ir.Block(self.builder.function, 'loopcond')
        loopbody_bb = ir.Block(self.builder.function, 'loopbody')
        loopafter_bb = ir.Block(self.builder.function, 'loopafter')

        # ###########
        # loop header
        #############

        # Save the current block to tell the loop cond where we are coming from
        # no longer needed, I think
        #loopheader_bb = self.builder.block

        # Jump to loop cond
        self.builder.branch(loopcond_bb)

        ###########
        # loop cond
        ###########

        self.builder.function.basic_blocks.append(loopcond_bb)
        self.builder.position_at_start(loopcond_bb)

        # Compute the end condition
        endcond = self._codegen(node.cond_expr)

        type = endcond.type

        # TODO: this requires different comparison operators
        # based on the type of the loop object - int vs. float, chiefly
        # this is a pattern we may repeat too often

        cond = ('!=', endcond, ir.Constant(type, 0), 'loopcond')

        if isinstance(type, (ir.FloatType, ir.DoubleType)):
            cmp = self.builder.fcmp_unordered(*cond)
        elif isinstance(type, ir.IntType):
            if getattr(type, 'v_signed', None):
                cmp = self.builder.icmp_signed(*cond)
            else:
                cmp = self.builder.icmp_unsigned(*cond)

        # Goto loop body if condition satisfied, otherwise, exit.
        self.builder.cbranch(cmp, loopbody_bb, loopafter_bb)

        ############
        # loop body
        ############

        self.builder.function.basic_blocks.append(loopbody_bb)
        self.builder.position_at_start(loopbody_bb)

        # Emit the body of the loop.
        body_val = self._codegen(node.body, False)

        # The value of the body has to be placed into a special
        # return variable so it's valid across all code paths
        self.builder.position_at_start(loopcond_bb)
        return_var = self.builder.alloca(
            body_val.type, size=None, name='%_while_loop_return')

        # Goto loop cond
        self.builder.position_at_end(loopbody_bb)
        self.builder.store(body_val, return_var)
        self.builder.branch(loopcond_bb)

        #############
        # loop after
        #############

        # New code will be inserted into a new block
        self.builder.function.basic_blocks.append(loopafter_bb)
        self.builder.position_at_start(loopafter_bb)

        # The 'while' expression returns the value of the body
        return self.builder.load(return_var)

    def _codegen_Call(self, node, obj_method=False):
        if not obj_method:
            if node.name in Builtins:
                return getattr(self, '_codegen_Builtins_' + node.name)(node)
            if node.name in Dunders:
                return self._codegen_dunder_methods(node)

        call_args = []
        possible_opt_args_funcs = set()

        # The reason for the peculiar construction below
        # is to first process a blank argument list, so
        # we can match calls to functions that have
        # all optional arguments

        for arg in node.args+[None]:
            _ = mangle_types(node.name, call_args)
            if _ in self.opt_args_funcs:
                possible_opt_args_funcs.add(self.opt_args_funcs[_])
            if arg:
                call_args.append(self._codegen(arg))

        if obj_method:
            c = call_args[0]
            try:
                c1 = c.type.pointee.name
            except:
                c1 = c.type
            node.name = f'{c1}.__{node.name}__'

        if not possible_opt_args_funcs:
            mangled_name = mangle_types(node.name, call_args)
            callee_func = self.module.globals.get(mangled_name, None)

        else:
            try:
                match = False
                for f1 in possible_opt_args_funcs:
                    if len(call_args) > len(f1.args):
                        continue
                    match = True
                    for function_arg, call_arg in zip(f1.args, call_args):
                        if function_arg.type != call_arg.type:
                            match = False
                            break
                if not match:
                    raise TypeError
            except TypeError:
                raise ParseError(
                    f'argument types do not match possible argument signature for optional-argument function "{f1.public_name}"',
                    node.position
                )
            else:
                callee_func = f1
                for n in range(len(call_args), len(f1.args)):
                    call_args.append(f1.args[n].default_value)

        # Determine if this is a function pointer

        try:
            
            # if we don't yet have a reference,
            # since this might be a function pointer,
            # attempt to obtain one from the variable list

            if not callee_func:
                callee_func = self._varaddr(node.name, False)

            if callee_func.type.is_func():
                # retrieve actual function pointer from the variable ref
                func_to_check = callee_func.type.pointee.pointee                
                final_call = self.builder.load(callee_func)
                ftype = func_to_check                
            else:
                # this is a regular old function, not a function pointer
                func_to_check = callee_func
                final_call = callee_func
                ftype = getattr(func_to_check, 'ftype', None)

        except Exception:
            raise CodegenError(
                f'Call to unknown function "{node.name}" with signature "{[n.type.describe() for n in call_args]}" (maybe this call signature is not implemented for this function?)',
                node.position)

        if not ftype.var_arg:
            if len(func_to_check.args) != len(call_args):
                raise CodegenError(
                    f'Call argument length mismatch for "{node.name}" (expected {len(callee_func.args)}, got {len(node.args)})',
                    node.position)
        else:
            if len(call_args) < len(func_to_check.args):
                raise CodegenError(
                    f'Call argument length mismatch for "{node.name}" (expected at least {len(callee_func.args)}, got {len(node.args)})',
                    node.position)

        for x, n in enumerate(zip(call_args, func_to_check.args)):
            type0 = n[0].type
            
            # in some cases, such as with a function pointer,
            # the argument is not an Argument but a core.vartypes instance
            # so this check is necessary

            if type(n[1])==ir.values.Argument:
                type1 = n[1].type
            else:
                type1 = n[1]

            if type0 != type1:
                raise CodegenError(
                    f'Call argument type mismatch for "{node.name}" (position {x}: expected {type1.describe()}, got {type0.describe()})',
                    node.args[x].position)

            # if this is a traced object, and we give it away,
            # then we can't delete it in this scope anymore
            # because we no longer have ownership of it
            
            to_check = self._extract_operand(n[0])        
            if to_check.heap_alloc:
                to_check.tracked = False

        call_to_return = self.builder.call(final_call, call_args, 'calltmp')

        # Check for the presence of an object returned from the call
        # that requires memory tracing

        if callee_func in self.gives_alloc:
            call_to_return.heap_alloc = True
            call_to_return.tracked = True

        return call_to_return

    def _codegen_Prototype(self, node):
        funcname = node.name

        # Create a function type

        vartypes = []
        vartypes_with_defaults = []

        append_to = vartypes

        for x in node.argnames:
            s = x.vartype
            if x.initializer is not None:
                append_to = vartypes_with_defaults
            append_to.append(s)

        # TODO: it isn't yet possible to have an implicitly
        # typed function that just uses the return type of the body
        # we might be able to do this by way of a special call
        # to this function
        # note that Extern functions MUST be typed

        if node.vartype is None:
            node.vartype = DEFAULT_TYPE

        functype = ir.FunctionType(
            node.vartype,
            vartypes+vartypes_with_defaults
        )

        public_name = funcname

        opt_args = None

        linkage = None

        # TODO: identify anonymous functions with a property
        # not by way of their nomenclature

        if node.extern is False and not funcname.startswith('_ANONYMOUS.') and funcname != 'main':
            linkage = 'private'
            if len(vartypes) > 0:
                funcname = public_name + mangle_args(vartypes)
            else:
                funcname = public_name + '@'

            required_args = funcname

            if len(vartypes_with_defaults) > 0:
                opt_args = mangle_optional_args(vartypes_with_defaults)
                funcname += opt_args

        # If a function with this name already exists in the module...
        if funcname in self.module.globals:

            # We only allow the case in which a declaration exists and now the
            # function is defined (or redeclared) with the same number of args.
            # TODO: I think this rule should be dropped and ANY prior
            # function version should never be overridden
            func = existing_func = self.module.globals[funcname]

            if not isinstance(existing_func, ir.Function):
                raise CodegenError(f'Function/universal name collision {funcname}',
                                   node.position)
            if not existing_func.is_declaration:
                raise CodegenError(
                    f'Redefinition of function "{public_name}"', node.position)
            if len(existing_func.function_type.args) != len(functype.args):
                raise CodegenError(
                    f'Redefinition of function "{public_name}" with different number of arguments',
                    node.position)
        else:
            # Otherwise create a new function

            func = ir.Function(self.module, functype, funcname)

            # Name the arguments
            for i, arg in enumerate(func.args):
                arg.name = node.argnames[i].name

        if opt_args is not None:
            self.opt_args_funcs[required_args] = func

        # Set defaults (if any)

        for x, n in enumerate(node.argnames):
            if n.initializer is not None:
                func.args[x].default_value = self._codegen(
                    n.initializer, False)

        if node.varargs:
            func.ftype.var_arg = True

        func.public_name = public_name

        func.returns = []

        ##############################################################
        # Set LLVM function attributes
        ##############################################################

        # First, extract a copy of the function decorators
        # and use that to set up other attributes

        decorators = [n.name for n in self.func_decorators]

        varfunc = 'varfunc' in decorators

        for a, b in decorator_collisions:
            if a in decorators and b in decorators:
                raise CodegenError(
                    f'Function cannot be decorated with both "@{a}" and "@{b}"',
                    node.position
                )

        # Calling convention.
        # This is the default with no varargs

        if node.varargs is None:
            func.calling_convention = 'fastcc'

        # Linkage.
        # Default is 'private' if it's not extern, an anonymous function, or main

        if linkage:
            func.linkage = linkage

        # Address is not relevant by default
        func.unnamed_addr = True

        # Enable optnone for main() or anything
        # designated as a target for a function pointer.
        if funcname == 'main' or varfunc:
            func.attributes.add('optnone')
            func.attributes.add('noinline')

        # Inlining. Operator functions are inlined by default.

        if (
            # function is manually inlined
            ('inline' in decorators)
            or
            # function is an operator, not @varfunc,
            # and not @noinline
            (node.isoperator and not varfunc and 'noinline' not in decorators)
        ):
            func.attributes.add('alwaysinline')

        # function is @noinline
        # or function is @varfunc
        if 'noinline' in decorators:
            func.attributes.add('noinline')

        # End inlining.

        # External calls, by default, no recursion
        if node.extern:
            func.attributes.add('norecurse')

        # By default, no lazy binding
        func.attributes.add('nonlazybind')

        # By default, no stack unwinding
        func.attributes.add('nounwind')

        func.decorators = decorators

        return func

    def _codegen_Function(self, node):

        # Reset the symbol table. Prototype generation will pre-populate it with
        # function arguments.
        self.func_symtab = {}

        # Create the function skeleton from the prototype.
        func = self._codegen(node.proto, False)

        # Create the entry BB in the function and set a new builder to it.
        bb_entry = func.append_basic_block('entry')
        self.builder = ir.IRBuilder(bb_entry)

        self.func_incontext = func
        self.func_returncalled = False
        self.func_returntype = func.return_value.type
        self.func_returnblock = func.append_basic_block('exit')
        self.func_returnarg = self._alloca('%_return', self.func_returntype)

        # Add all arguments to the symbol table and create their allocas
        for _, arg in enumerate(func.args):
            if arg.type.is_obj_ptr():
                alloca = arg                
            else:
                alloca = self._alloca(arg.name, arg.type)
                self.builder.store(arg, alloca)            

            # We don't shadow existing variables names, ever
            assert not self.func_symtab.get(arg.name) and "arg name redefined: " + arg.name
            self.func_symtab[arg.name] = alloca
            
            alloca.input_arg = _            
            alloca.tracked = False

        # Generate code for the body
        retval = self._codegen(node.body, False)

        if retval is None and self.func_returncalled is True:
            # we don't need to check for a final returned value,
            # because it's implied that there's an early return
            pass
        else:
            if not hasattr(retval, 'type'):
                raise CodegenError(
                    f'Function "{node.proto.name}" has a return value of type "{func.return_value.type.describe()}" but no concluding expression with an explicit return type was supplied',
                    node.position)

            if retval is None and func.return_value.type is not None:
                raise CodegenError(
                    f'Function "{node.proto.name}" has a return value of type "{func.return_value.type.describe()}" but no expression with an explicit return type was supplied',
                    node.position)

            if func.return_value.type != retval.type:
                if node.proto.name.startswith(_ANONYMOUS):
                    func.return_value.type = retval.type
                    self.func_returnarg = self._alloca('%_return', retval.type)
                else:
                    raise CodegenError(
                        f'Prototype for function "{node.proto.name}" has return type "{func.return_value.type.describe()}", but returns "{retval.type.describe()}" instead (maybe an implicit return?)',
                        node.proto.position)

            self.builder.store(retval, self.func_returnarg)
            self.builder.branch(self.func_returnblock)

        self.builder = ir.IRBuilder(self.func_returnblock)
        
        # Check for the presence of a returned object
        # that requires memory tracing
        # if so, add it to the set of functions that returns a trackable object

        to_check = retval

        if retval:
            to_check = self._extract_operand(retval)
            if to_check.tracked:
                self.gives_alloc.add(self.func_returnblock.parent)
                self.func_returnblock.parent.returns.append(to_check)

        # Determine which variables need to be automatically disposed
        
        if to_check:
            for _,v in reversed(list(self.func_symtab.items())):
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
                    ref2 = self.builder.bitcast( # pylint: disable=E1111
                        ref,
                        VarTypes.u_size.as_pointer()
                    )
                    sig = v.type.pointee.pointee.signature()
                    
                    self.builder.call(
                        self.module.globals.get(sig+'__del__'),
                        [ref2],
                        'del'
                    )                    

        self.builder.ret(self.builder.load(self.func_returnarg))

        self.func_incontext = None
        self.func_returntype = None
        self.func_returnarg = None
        self.func_returnblock = None
        self.func_returncalled = None        

    def _codegen_Unary(self, node):
        operand = self._codegen(node.rhs)
        # TODO: no overflow checking yet!
        if node.op in BUILTIN_UNARY_OP:
            if node.op == 'not':
                if isinstance(operand.type, (ir.IntType, ir.DoubleType)):
                    cond_expr = Binary(node.position, '==', node.rhs,
                                       Number(node.position, 0, operand.type))
                    return self._codegen_If(
                        If(
                            node.position,
                            cond_expr,
                            Number(node.position, 1, operand.type),
                            Number(node.position, 0, operand.type), ))
            elif node.op == '-':
                lhs = ir.Constant(operand.type, 0)
                if isinstance(operand.type, ir.IntType):
                    return self.builder.sub(lhs, operand, 'negop')
                elif isinstance(operand.type, ir.DoubleType):
                    return self.builder.fsub(lhs, operand, 'fnegop')
        else:
            func = self.module.globals.get(
                f'unary.{node.op}{mangle_args((operand.type,))}')
            if not func:
                raise CodegenError(
                    f'Undefined unary operator "{node.op}" for "{operand.type.describe()}"',
                    node.position)
            return self.builder.call(func, [operand], 'unop')

    def _codegen_Var(self, node):
        for v in node.vars:

            name = v.name
            v_type = v.vartype
            expr = v.initializer
            position = v.position

            val, v_type = self._codegen_VarDef(expr, v_type)

            var_ref = self.func_symtab.get(name)
            if var_ref is not None:
                raise CodegenError(f'"{name}" already defined in local scope',
                                   position)

            var_ref = self.module.globals.get(name, None)
            if var_ref is not None:
                raise CodegenError(
                    f'"{name}" already defined in universal scope', position)

            var_ref = self._alloca(name, v_type)
            
            if val:
                var_ref.heap_alloc = val.heap_alloc
                var_ref.input_arg = val.input_arg

                if var_ref.heap_alloc:
                    var_ref.tracked = True

            self.func_symtab[name] = var_ref

            if expr:

                # if _do_not_allocate is set, we've already preallocated space
                # for the object, so all we have to do is set the name
                # to its existing pointer

                if val.do_not_allocate:
                    self.func_symtab[name] = val
                else:
                    self.builder.store(val, var_ref)

            else:
                if v_type.is_obj_ptr():
                    if not isinstance(v_type.pointee, ir.FunctionType):
                        # allocate the actual object, not just a pointer to it
                        # beacuse it doesn't actually exist yet!
                        obj = self._alloca('obj', v_type.pointee)
                        self.builder.store(obj, var_ref)

    def _codegen_VarDef(self, expr, vartype):
        if expr is None:
            val = None
            if vartype is None:
                vartype = DEFAULT_TYPE
            final_type = vartype
        else:
            val = self._codegen(expr)

            if vartype is None:
                vartype = val.type

            if vartype == ir.types.FunctionType:
                pass
                # instead of conventional codegen, we generate the fp here

            if val.type != vartype:
                raise CodegenError(
                    f'Type declaration and variable assignment type do not match (expected "{vartype.describe()}", got "{val.type.describe()}"',
                    expr.position)
            if val.type.signed != vartype.signed:
                raise CodegenError(
                    f'Type declaration and variable assignment type have signed/unsigned mismatch (expected "{vartype.describe()}", got "{val.type.describe()}")',
                    expr.position)

            final_type = val.type

        return val, final_type

    def _codegen_Uni(self, node, const=False):
        for name, vartype, expr, position in node.vars:

            var_ref = self.module.globals.get(name, None)

            if var_ref is not None:
                raise CodegenError(
                    f'Duplicate found in universal symbol table: "{name}"',
                    position)

            if const and expr is None:
                raise CodegenError(
                    f'Constants must have an assignment: "{name}"', position)

            val, final_type = self._codegen_VarDef(expr, vartype)

            if final_type is None:
                final_type = DEFAULT_TYPE

            str1 = ir.GlobalVariable(self.module, final_type, name)

            if const:
                str1.global_constant = True
            if val is None:
                if final_type.is_obj_ptr():
                    empty_obj = ir.GlobalVariable(
                        self.module,
                        final_type.pointee,
                        name + '.init'
                    )
                    empty_obj.initializer = ir.Constant(
                        final_type.pointee, None)
                    str1.initializer = empty_obj
                else:
                    str1.initializer = ir.Constant(final_type, None)
            else:
                str1.initializer = val

    def _codegen_Const(self, node):
        return self._codegen_Uni(node, True)

    def _codegen_Do(self, node):
        for n in node.expr_list:
            try:
                t = self._codegen(n, False)
            except CodegenError as e:
                raise e
        return t

    def _codegen_With(self, node):
        old_bindings = []

        for v in node.vars.vars:

            name = v.name
            v_type = v.vartype
            init = v.initializer
            position = v.position

            # Emit the initializer before adding the variable to scope. This
            # prevents the initializer from referencing the variable itself.

            if self._varaddr(name, False) is not None:
                raise CodegenError(
                    f'Variable shadowing is not permitted; "{name}" is used in other scopes',
                    position)

            val, final_type = self._codegen_VarDef(init, v_type)

            var_addr = self._alloca(name, final_type, current_block=True)

            if val is not None:
                self.builder.store(val, var_addr)

            # Put var in symbol table; remember old bindings if any.
            old_bindings.append(self.func_symtab.get(name))
            self.func_symtab[name] = var_addr

        # Now all the vars are in scope. Codegen the body.
        body_val = self._codegen(node.body)

        # TODO: Delete anything that has gone out of scope,
        # as per how we handle a function.

        # Restore the old bindings.
        for i, v in enumerate(node.vars.vars):
            name = v.name
            if old_bindings[i] is not None:
                self.func_symtab[name] = old_bindings[i]
            else:
                del self.func_symtab[name]

        return body_val

    def _codegen_dunder_methods(self, node):
        call = self._codegen_Call(
            Call(node.position, node.name,
                 node.args,
                 ),
            obj_method=True
        )
        return call

#######################################################
# Builtins
#######################################################

    def _check_pointer(self, obj, node):
        '''
        Determines if a given item is a pointer or object.
        '''
        if not isinstance(obj.type, ir.PointerType):
            raise CodegenError('Parameter must be a pointer or object',
                               node.args[0].position)

    def _get_obj_noload(self, node, ptr_check=True):
        '''
        Returns a pointer to a codegenned object.
        '''
        arg = node.args[0]
        if isinstance(arg, Variable):
            codegen = self._codegen_Variable(arg, noload=True)
        else:
            codegen = self._codegen(arg)
        if ptr_check:
            self._check_pointer(codegen, node)
        return codegen

    def _codegen_Builtins_c_obj_alloc(self, node):
        '''
        Allocates bytes for an object of the type submitted.
        Eventually we will be able to submit a type directly.
        For now, use a throwaway closure that generates
        an object of the type you want to use
        E.g., for an i32[8]:
        var x=c_obj_alloc({with var z:i32[8] z})
        (the contents of the closure are optimized out
        at compile time)
        '''

        expr = self._get_obj_noload(node)
        e2 = self.builder.load(expr)
        sizeof = self._obj_size(e2)

        call = self._codegen_Call(
            Call(node.position, 'c_alloc',
                 [Number(node.position, sizeof, VarTypes.u_size)]))

        b1 = self.builder.bitcast(call, expr.type) # pylint: disable=E1111
        b2 = self.builder.alloca(b1.type)
        self.builder.store(b1, b2)

        b2.do_not_allocate = True
        b2.heap_alloc = True
        b2.tracked = True

        return b2

    def _codegen_Builtins_c_obj_free(self, node):
        '''
        Deallocates memory for an object created with c_obj_alloc.
        '''
        expr = self._get_obj_noload(node)

        if not expr.tracked:
            raise CodegenError(f'{node.args[0].name} is not an allocated object',node.args[0].position)

        # Mark the variable in question as untracked
        expr.tracked = False

        addr = self.builder.load(expr)
        addr2 = self.builder.bitcast(addr, VarTypes.u_size.as_pointer()).get_reference()

        call = self._codegen_Call(
            Call(node.position, 'c_free',
                 [Number(node.position, addr2,
            VarTypes.u_size.as_pointer())]))        

        return call

    def _codegen_Builtins_c_obj_ref(self, node):
        '''
        Returns a typed pointer to the object.
        '''
        expr = self._get_obj_noload(node)
        s1 = self._alloca('obj_ref', expr.type)
        self.builder.store(expr, s1)
        return s1

    def _codegen_Builtins_c_size(self, node):
        '''
        Returns the size of the object's descriptor in bytes.
        For a string, this is NOT the size of the
        underlying string, but the size of the *structure*
        that describes a string.
        '''
        expr = self._codegen(node.args[0])

        if expr.type.is_obj_ptr():
            s1 = expr.type.pointee
        else:
            s1 = expr.type

        s2 = self._obj_size_type(s1)

        return ir.Constant(VarTypes.u_size, s2)

    def _codegen_Builtins_c_obj_size(self, node):
        # eventually we'll extract this information from
        # the object headers once we start using those regularly

        convert_from = self._get_obj_noload(node)

        # get direct pointer to object
        s0 = self.builder.load(convert_from)

        # get actual data element pointer
        s1 = self.builder.gep(
            s0,
            [
                self._i32(0),
                self._i32(1)
            ]
        )

        # dereference that to get the underlying data element
        s1 = self.builder.load(s1)

        # determine its size
        s2 = self._obj_size_type(s1.type)

        return ir.Constant(VarTypes.u_size, s2)

    def _codegen_Builtins_c_data(self, node):
        '''
        Returns the underlying C-style data element
        for an object.
        This will eventually be normalized to be element 1 in the
        GEP structure for the object, to make it easy to extract
        that element universally.
        '''
        convert_from = self._codegen(node.args[0])

        gep = self.builder.gep(
            convert_from,
            [
                self._i32(0),
                self._i32(1),
            ]
        )

        gep = self.builder.load(gep)
        return gep

    def _codegen_Builtins_c_array_ptr(self, node):
        '''
        Returns a raw u_size pointer to the start of an array object.
        NOTE: I think we can merge this with c_data,
        since they are essentially the same thing, once we normalize
        the layout of string and array objects.
        '''
        convert_from = self._get_obj_noload(node)

        convert_from = self.builder.load(convert_from)
        gep = self.builder.gep(
            convert_from,
            [self._i32(0),self._i32(1),]
        )
        bc = self.builder.bitcast(gep, VarTypes.u_size.as_pointer()) # pylint: disable=E1111
        return bc

    def _codegen_Builtins_c_addr(self, node):
        '''
        Returns an unsigned value that is the address of the object in memory.
        '''
        address_of = self._get_obj_noload(node)
        return self.builder.ptrtoint(address_of, VarTypes.u_size)

        # perhaps we should also have a way to cast
        # c_addr as a pointer to a specific type (the reverse of this)

    def _codegen_Builtins_c_deref(self, node):
        '''
        Dereferences a pointer to a primitive, like an int.
        '''

        ptr = self._get_obj_noload(node)
        ptr2 = self.builder.load(ptr)

        if hasattr(ptr2.type, 'pointee'):
            ptr2 = self.builder.load(ptr2)

        if hasattr(ptr2.type, 'pointee'):
            raise CodegenError(
                f'"{node.args[0].name}" is not a reference to a scalar (use c_obj_deref for references to objects instead of scalars)',
                node.args[0].position)

        return ptr2

    def _codegen_Builtins_c_ref(self, node):
        '''
        Returns a typed pointer to a primitive, like an int.
        '''

        expr = self._get_obj_noload(node)

        if expr.type.is_obj_ptr():
            raise CodegenError(
                f'"{node.args[0].name}" is not a scalar (use c_obj_ref for references to objects instead of scalars)',
                node.args[0].position)

        return expr

    def _codegen_Builtins_c_obj_deref(self, node):
        '''
        Dereferences a pointer (itself passed as a pointer)
        and returns the object at the memory location.
        '''

        ptr = self._codegen(node.args[0])
        ptr2 = self.builder.load(ptr)
        self._check_pointer(ptr2, node)
        ptr3 = self.builder.load(ptr2)
        return ptr3

    def _codegen_Builtins_cast(self, node):
        '''
        Cast one data type as another, such as a pointer to a u64,
        or an i8 to a u32.
        Ignores signing.
        Will truncate bitwidths.
        '''

        cast_from = self._codegen(node.args[0])
        cast_to = self._codegen(node.args[1], False)

        cast_exception = CodegenError(
            f'Casting from type "{cast_from.type.describe()}" to type "{cast_to.describe()}" is not supported',
            node.args[0].position)

        while True:

            # If we're casting FROM a pointer...

            if isinstance(cast_from.type, ir.PointerType):

                # it can't be an object pointer (for now)
                if cast_from.type.is_obj_ptr():
                    raise cast_exception

                # but it can be cast to another pointer
                # as long as it's not an object
                if isinstance(cast_to, ir.PointerType):
                    if cast_to.is_obj_ptr():
                        raise cast_exception
                    op = self.builder.bitcast
                    break

                # and it can't be anything other than an int
                if not isinstance(cast_to, ir.IntType):
                    raise cast_exception

                # and it has to be the same bitwidth
                if self.pointer_bitwidth != cast_to.width:
                    raise cast_exception

                op = self.builder.ptrtoint
                break

            # If we're casting TO a pointer ...

            if isinstance(cast_to, ir.PointerType):

                # it can't be from anything other than an int
                if not isinstance(cast_from.type, ir.IntType):
                    raise cast_exception

                # and it has to be the same bitwidth
                if cast_from.type.width != self.pointer_bitwidth:
                    raise cast_exception

                op = self.builder.inttoptr
                break

            # If we're casting non-pointers of the same bitwidth,
            # just use bitcast

            if cast_from.type.width == cast_to.width:
                op = self.builder.bitcast
                break

            # If we're going from a smaller to a larger bitwidth,
            # we need to use the right instruction

            if cast_from.type.width < cast_to.width:
                if isinstance(cast_from.type, ir.IntType):
                    if isinstance(cast_to, ir.IntType):
                        op = self.builder.zext
                        break
                    if isinstance(cast_to, ir.DoubleType):
                        if cast_from.type.signed:
                            op = self.builder.sitofp
                            break
                        else:
                            op = self.builder.uitofp
                            break
            else:
                op = self.builder.trunc
                break
                #cast_exception.msg += ' (data would be truncated)'
                #raise cast_exception

            raise cast_exception

        result = op(cast_from, cast_to)
        result.type = cast_to
        return result

    def _codegen_Builtins_convert(self, node):
        '''
        Converts data between primitive value types, such as i8 to i32.
        Checks for signing and bitwidth.
        Conversions from or to pointers are not supported here.
        '''
        convert_from = self._codegen(node.args[0])
        convert_to = self._codegen(node.args[1], False)

        convert_exception = CodegenError(
            f'Converting from type "{convert_from.type.describe()}" to type "{convert_to.describe()}" is not supported',
            node.args[0].position)

        while True:

            # Conversions from/to an object are not allowed

            if convert_from.type.is_obj_ptr() or convert_to.is_obj_ptr():
                explanation = f'\n(Converting from/to object types will be added later.)'
                convert_exception.msg += explanation
                raise convert_exception

            # Convert from/to a pointer is not allowed

            if isinstance(convert_from.type, ir.PointerType) or isinstance(convert_to, ir.PointerType):
                convert_exception.msg += '\n(Converting from or to pointers is not allowed; use "cast" instead)'
                raise convert_exception

            # Convert from float to int is OK, but warn

            if isinstance(convert_from.type, ir.DoubleType):

                if not isinstance(convert_to, ir.IntType):
                    raise convert_exception

                print(
                    CodegenWarning(
                        f'Float to integer conversions ("{convert_from.type.describe()}" to "{convert_to.describe()}") are inherently imprecise',
                        node.args[0].position))

                if convert_from.type.signed:
                    op = self.builder.fptosi
                else:
                    op = self.builder.fptoui
                break

            # Convert from ints

            if isinstance(convert_from.type, ir.IntType):

                # int to float

                if isinstance(convert_to, ir.DoubleType):
                    print(
                        CodegenWarning(
                            f'Integer to float conversions ("{convert_from.type.describe()}" to "{convert_to.describe()}") are inherently imprecise',
                            node.args[0].position))

                    if convert_from.type.signed:
                        op = self.builder.sitofp
                    else:
                        op = self.builder.uitofp
                    break

                # int to int

                if isinstance(convert_to, ir.IntType):

                    # Don't allow mixing signed/unsigned

                    if convert_from.type.signed and not convert_to.signed:
                        raise CodegenError(
                            f'Signed type "{convert_from.type.describe()}" cannot be converted to unsigned type "{convert_to.describe()}"',
                            node.args[0].position)

                    # Don't allow converting to a smaller bitwidth

                    if convert_from.type.width > convert_to.width:
                        raise CodegenError(
                            f'Type "{convert_from.type.describe()}" cannot be converted to type "{convert_to.describe()}" without possible truncation',
                            node.args[0].position)

                    # otherwise, extend bitwidth to convert

                    if convert_from.type.signed:
                        op = self.builder.sext
                    else:
                        op = self.builder.zext
                    break

            raise convert_exception

        result = op(convert_from, convert_to)
        result.type = convert_to
        return result
    
    def _codegen_Builtins_print_statement(self, node):
        pass

        # print takes 1 or more f-strings
        # for each f-string:
        # split from left to right, starting with {
        # if there are no vars, just use the string as-is
        # and return early
        # if there is no corresponding }, crash
        # codegen the name so we can use func-calls
        # if not found, crash
        # look up the type for the symbol
        # substitute the appropriate formatter
        # construct the new string
        # construct a new call to the underlying printf
        # add spacer for next iteration of the loop
        
        # be sure to escape literals - how to do that?
        # maybe we could do that in the lexing portion,
        # and store the results with the string node
        # seems like the best way to do it
        # store strings in one list, variables in another
        # use zip to concatenate them as needed

        # another way to do it: store the string as-is,
        # but if we encounter {}, set a flag for it
        # and then retrieve a split version of the string
        # on demand when we need it
        # by way of a helper function