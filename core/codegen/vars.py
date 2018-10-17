import llvmlite.ir as ir
from core.errors import CodegenError
from core.ast_module import Variable, Call, ArrayAccessor, Number, ItemList
from core.mangling import mangle_call
#from core.vartypes import VarTypes, DEFAULT_TYPE
from core.vartypes import ArrayClass

# pylint: disable=E1101


class Vars():
    def _codegen_NoneType(self, node):
        pass

    def _codegen_Number(self, node):
        if type(node.val)==str:
            raise Exception()
        num = ir.Constant(node.vartype, node.val)
        return num

    def _codegen_VariableType(self, node):
        return node.vartype

    def _codegen_AllocaInstr(self, node):
        return node

    def _codegen_CastInstr(self, node):
        return node

    def _codegen_GlobalVariable(self, node):
        return node
    
    def _codegen_ArrayAccessor(self, node):
        return self._codegen_Call(
            Call(
                node.position,
                "index",
                [
                    self.last_inline
                ]+node.elements,
            ),
            obj_method=True,                        
        )

    def _codegen_ArrayElement(self, node, array):
        '''
        Returns a pointer to the requested element of an array.
        '''

        elements = [self._codegen(n) for n in node.elements]

        accessor = [
            self._i32(0),
            self._i32(1),
        ] + elements

        # First, try to obtain a conventional array accessor element

        try:
            ptr = self.builder.gep(array, accessor, False, f'{array.name}')
        except Exception as e:
            pass
        else:
            return ptr

        # If that fails, assume we're trying to manually index an object

        if not self.allow_unsafe:
            raise CodegenError(
                f'Accessor "{array.name}" into unindexed object requires "unsafe" block',
                node.position)
        try:
            ptr = self.builder.gep(
                array, [self._i32(0)] + elements, False, f'{array.name}')
        except AttributeError as e:
            raise CodegenError(
                f'Unindexed accessor for "{array.name}" requires a constant',
                node.position)
        except Exception:
            pass
        else:
            return ptr

        # If that fails, abort

        raise CodegenError(
            f'Invalid array accessor for "{array.name}" (maybe wrong number of dimensions?)',
            node.position)

    def _codegen_LoadInstr(self, node):
        return node

    def _codegen_Variable(
            self, node,
            noload=False,
            start_with=None
        ):

        current_node = node

        # If we're not starting with a root variable,
        # such as an inline string, we need to use
        # `start_with` to indicate that
        
        if start_with:
            previous_node, previous, latest = start_with
        else:
            previous_node = None
            # previous AST node
            previous = None
            # previous codegenned variable
            latest = None
            # latest codegenned variable

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
                
                if isinstance(latest.type.pointee, ArrayClass):
                    # manually generate array index lookup                    
                    latest = self._codegen_ArrayElement(
                        current_node, array_element)
                    current_load = not latest.type.is_obj_ptr()
                
                else:
                    # attempt __index__ call on the object
                    latest = self._codegen_Call(
                        Call(
                            previous_node.position,
                            "index",
                            [
                                previous
                            ]+current_node.elements,
                        ),
                        obj_method=True,                        
                    )
                    current_load = False


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
                    raise CodegenError(
                        f'Not a pointer or object', current_node.position)

                _latest_vid = oo.v_id
                _cls = self.class_symtab[_latest_vid]
                _pos = _cls.v_types[current_node.name]['pos']

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
                raise CodegenError(
                    f'Unknown variable instance', current_node.position)

            child = getattr(current_node, 'child', None)
            if child is None:
                break

            if current_load:
                latest = self.builder.load(latest, node.name+'.accessor')

            previous_node = current_node
            current_node = child
            previous = latest

        if noload is True:
            return latest

        if current_load:

            # Extract constants from uni declarations
            possible_constant = self._extract_operand(latest)
            if isinstance(possible_constant, ir.GlobalVariable) and possible_constant.global_constant is True:
                return possible_constant.initializer

            # if no constant, just return a load instr
            return self.builder.load(latest, node.name)

        else:
            return latest

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
            if not value:
                raise CodegenError(
                    f'Call to unknown function "{rhs.name}" with signature {[n.describe() for n in ptr.type.pointee.pointee.args]}" (maybe this call signature is not implemented for this function?)',
                    rhs.position)
            if 'varfunc' not in value.decorators:
                raise CodegenError(
                    f'Function "{rhs.name}" must be decorated with "@varfunc" to allow variable assignments',
                    rhs.position
                )

            #ptr.decorators = value.decorators
            # XXX: Not possible to trace function decorators across
            # function pointer boundaries
            # One POSSIBLE way to do it would be to have a specialized type
            # that uses the function decorators mangled in the name.
            # That way the pointer could only point to one of a class of
            # function pointers allowed to do so (with bitcasting).
            # But this seems like a lot of work for little payoff.

        else:
            value = self._codegen(rhs)

        if self.allow_unsafe:
            if ptr.type.pointee != value.type:
                value = self.builder.bitcast(
                    value,
                    ptr.type.pointee
                )

        if ptr.type.pointee != value.type:
            if getattr(lhs, 'accessor', None):
                error_string = f'Cannot assign value of type "{value.type.describe()}" to element of array "{ptr.pointer.name}" of type "{ptr.type.pointee.describe()}"'
            else:
                error_string = f'Cannot assign value of type "{value.type.describe()}" to variable "{ptr.name}" of type "{ptr.type.pointee.describe()}"',
            raise CodegenError(error_string, rhs.position)

        self.builder.store(value, ptr)

        return value

    def _codegen_String(self, node):
        current = self._string_base(node.val)
        if hasattr(node,"child"):
            return self._codegen_Variable(node.child,
                start_with=[
                    node,
                    current,
                    current,
                ]
            )
        return current

    def _string_base(self, string, global_constant=True):
        '''
        Core function for code generation for strings.        
        This will also be called when we create strings dynamically
        in the course of a function, or statically during compilation.
        '''
        # only strings codegenned from source should be stored as LLVM globals
        module = self.module
        string_length = len(string.encode('utf8')) + 1
        data_type = ir.ArrayType(ir.IntType(8), string_length)

        str_name = f'.str.{len(module.globals)}'

        # Create the LLVM constant value for the underlying string data.

        str_const = ir.GlobalVariable(module, data_type, str_name + '.dat')
        str_const.storage_class = 'private'
        str_const.unnamed_addr = True
        str_const.global_constant = True

        str_const.initializer = ir.Constant(
            data_type,
            bytearray(string, 'utf8') + b'\x00')

        # Get pointer to first element in string's byte array
        # and bitcast it to a ptr i8.

        spt = str_const.gep([self._int(0)]).bitcast(
            self.vartypes.u_mem.as_pointer())

        # Create the string object that points to the constant.

        str_val = ir.GlobalVariable(module, self.vartypes.str, str_name)
        str_val.storage_class = 'private'
        str_val.unnamed_addr = True
        str_val.global_constant = True

        # Set the string object data.
        #t1 = self.builder.inttoptr(None,self.vartypes.u_mem.as_pointer())

        str_val.initializer = self.vartypes.str(
            [[
                ir.Constant(self.vartypes.u64, string_length),
                spt,
                ir.Constant(self.vartypes.u64, 0),
                ir.Constant(self.vartypes.bool, 0),
                ir.Constant(self.vartypes.bool, 0)
                ]
            ,])

        return str_val        

    def _codegen_ItemList(self, node):
        base_vartype = None
        element_list = []

        for x in node.elements:
            if base_vartype is None:
                base_vartype = x.vartype
            elif base_vartype!=x.vartype:
                raise CodegenError(
                    f'Constant array definition is not of a consistent type (expected "{base_vartype.describe()}", got "{x.vartype.describe()}"',
                    x.position
                )
            try:
                element_list.append(ir.Constant(x.vartype, x.val))
            except AttributeError:
                raise CodegenError(
                    f'Constant array definition has an invalid element',
                    x.position
                )

        const = ir.Constant(
            self.vartypes.array(base_vartype, len(node.elements)),
            element_list
        )

        list_const = ir.GlobalVariable(self.module, const.type, f'.array_const.{self.const_counter()}')
        list_const.storage_class = 'private'
        list_const.unnamed_addr = True
        list_const.global_constant = True
        list_const.initializer = const
        
        return list_const

    def _codegen_Var(self, node, local_alloca=False):
        for v in node.vars:

            name = v.name
            v_type = v.vartype
            expr = v.initializer
            position = v.position

            var_ref = self.func_symtab.get(name)
            if var_ref is not None:
                raise CodegenError(f'"{name}" already defined in local scope',
                                   position)

            var_ref = self.module.globals.get(name, None)
            if var_ref is not None:
                raise CodegenError(
                    f'"{name}" already defined in universal scope', position)

            flag = False

            if isinstance(expr, ItemList):
                flag = True

                val = self._codegen(expr)

                # TODO: list_const count should not exceed size of target array

                if val.type.pointee.element != v_type.pointee.arr_type:
                    raise CodegenError(
                        f'Constant array type and variable definition do not match (constant array is "{val.type.pointee.element.describe()}" but variable is "{v_type.pointee.arr_type.describe()}")',
                        node.position
                    )

                element_width = (
                    val.type.pointee.element.width // self.vartypes._byte_width
                ) * len(expr.elements)

                var_ref = self._alloca(name, v_type.pointee, current_block=local_alloca)

                # Get the pointer to the data area for the array
                sub_var_ref = self.builder.gep(
                    var_ref,
                    [self._i32(0),
                    self._i32(1),]
                )

                sub_var_ref = self.builder.bitcast(     
                    sub_var_ref,
                    self.vartypes.u_mem.as_pointer()
                )

                sub_val = self.builder.bitcast(     
                    val,
                    self.vartypes.u_mem.as_pointer()
                )

                # Copy the constant into the data area                
                llvm_memcpy = self.module.declare_intrinsic(
                    'llvm.memcpy',
                    [self.vartypes.u_mem.as_pointer(),
                    self.vartypes.u_mem.as_pointer(),
                    self.vartypes.u_size
                    ]
                )

                self.builder.call(
                    llvm_memcpy,
                    [
                        sub_var_ref,
                        sub_val,
                        ir.Constant(
                            self.vartypes.u64,
                            element_width
                        ),
                        ir.Constant(
                            # default alignment
                            self.vartypes.u32,
                            0
                        ),
                        ir.Constant(
                            ir.IntType(1),
                            False
                        )
                    ],
                    '.memcpy.' 
                )
                val.do_not_allocate=True
                
            else:
                val, v_type = self._codegen_VarDef(expr, v_type)
                var_ref = self._alloca(name, v_type, current_block=local_alloca)

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
                
                if not flag:

                    if val.do_not_allocate:
                        self.func_symtab[name] = val
                    else:
                        self.builder.store(val, var_ref)

            else:
                # if this is an object pointer,
                # allocate an empty object to it

                if v_type.is_obj_ptr():
                    if not isinstance(v_type.pointee, ir.FunctionType):
                        # allocate the actual object, not just a pointer to it
                        # because it doesn't actually exist yet!

                        obj = self._alloca('obj', v_type.pointee)
                        self.builder.store(obj, var_ref)
                        
                # if this is another kind of pointer,
                # any uninitialized pointer should be nulled

                elif v_type.is_ptr():                    
                    zeroinit = self._codegen(
                        Number(
                            v.position,
                            0,
                            self.vartypes.u_size
                        )
                    )
                    z2 = self.builder.inttoptr(zeroinit,
                        var_ref.type.pointee)
                    self.builder.store(z2, var_ref)
                
                # null any existing scalar types
                # note that we don't zero arrays yet

                else:
                    zeroinit = self._codegen(
                        Number(
                            v.position,
                            0,
                            v_type
                        )
                    )
                    self.builder.store(zeroinit, var_ref)

    def _codegen_VarDef(self, expr, vartype):
        if expr is None:
            val = None
            if vartype is None:
                vartype = self.vartypes._DEFAULT_TYPE
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
