import llvmlite.ir as ir
from core.errors import CodegenError, CodegenWarning
from core.ast_module import Variable, Call, ArrayAccessor, Number, ItemList, Global, String, Number, ItemList, FString, Unsafe
from core.mangling import mangle_call
from core.vartypes import ArrayClass

# pylint: disable=E1101

class Vars():
    def _codegen_NoneType(self, node):
        pass

    def _codegen_Number(self, node):
        num = ir.Constant(node.vartype, node.val)
        return num

    def _codegen_VariableType(self, node):
        return node.vartype

    def _codegen_Constant(self, node):
        return node

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
                f'Unindexed accessor for "{array.name}" requires a compile-time constant',
                node.position)
        except Exception as e:
            raise e
        else:
            return ptr

        # If that fails, abort

        raise CodegenError(
            f'Invalid array accessor for "{array.name}" (maybe wrong number of dimensions?)',
            node.position)

    def _codegen_LoadInstr(self, node):
        return node

    def _codegen_Variable(self, node, noload=False, start_with=None):

        current_node = node

        constant = False

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

                if constant is False:
                    constant = getattr(latest,'global_constant', False)

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
                
                # TODO: why is a call the exception for current_load?

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
            latest.global_constant = constant
            return latest

        if current_load:

            # Extract constants from uni declarations
            # XXX: I've removed this for the time being because it caused
            # problems where a constant variable like an array had
            # the wrong elements extracted

            # possible_constant = self._extract_operand(latest)
            # if isinstance(possible_constant, ir.GlobalVariable) and possible_constant.global_constant is True:
            #     return possible_constant.initializer

            # if no constant, just return a load instr
            final = self.builder.load(latest, node.name)

        else:
            final = latest

        final.global_constant = constant

        return final

    def _codegen_String(self, node):
        current = self._string_base(node)
        if hasattr(node, "child"):
            return self._codegen_Variable(
                node.child, start_with=[
                    node, current, current, ]
            )
        return current

    def _string_base(self, node, global_constant=True):
        '''
        Core function for code generation for strings.        
        This will also be called when we create strings dynamically
        in the course of a function, or statically during compilation.
        '''
        # only strings codegenned from source should be stored as LLVM globals
        string = node.val
        module = self.module
        string_length = len(string.encode('utf8')) + 1
        data_type = ir.ArrayType(ir.IntType(8), string_length)

        str_name = f'.str.{len(module.globals)}'

        # Create the LLVM constant value for the underlying string data.

        str_const = self._codegen(
            Global(node.position,
                   ir.Constant(
                       data_type,
                       bytearray(string, 'utf8') + b'\x00'),
                   f'{str_name}.dat',
                   global_constant=True
                   )
        )

        # Get pointer to first element in string's byte array
        # and bitcast it to a ptr i8.

        spt = str_const.gep([self._int(0)]).bitcast(
            self.vartypes.u_mem.as_pointer())

        # Set the string object data.

        initializer = self.vartypes.str(
            [[
                ir.Constant(self.vartypes.u64, string_length),
                spt,
                ir.Constant(self.vartypes.u64, self.vartypes.str.enum_id),
                ir.Constant(self.vartypes.bool, 0),
                ir.Constant(self.vartypes.bool, 0)
            ], ])

        # Create the string object that points to the constant.

        str_val = self._codegen(
            Global(node.position,
                   initializer,
                   str_name,
                   global_constant=True
                   )
        )

        return str_val

    def _codegen_ItemList(self, node):
        base_vartype = None
        element_list = []

        for element in node.elements:
            if base_vartype is None:
                base_vartype = element.vartype
            elif base_vartype != element.vartype:
                raise CodegenError(
                    f'Constant array definition is not of a consistent type (expected "{base_vartype.describe()}", got "{x.vartype.describe()}"',
                    element.position
                )
            try:
                element_list.append(ir.Constant(element.vartype, element.val))
            except AttributeError:
                raise CodegenError(
                    f'Constant array definition has an invalid element',
                    element.position
                )

        const = ir.Constant(
            self.vartypes._carray(base_vartype, len(node.elements)),
            element_list
        )

        return self._codegen(
            Global(node.position, const)
        )

    def _codegen_Global(self, node):
        if node.name is None:
            node.name = f'.const.{self.const_counter()}'

        global_var = ir.GlobalVariable(self.module, node.const.type, node.name)
        global_var.storage_class = 'private'
        global_var.unnamed_addr = True
        global_var.global_constant = node.global_constant
        if node.const:
            global_var.initializer = node.const

        return global_var

    def _codegen_create_variable(self, node, local_alloca=False):

        var_name = node.name
        var_type = node.vartype
        position = node.position

        var_ref = self.func_symtab.get(var_name)
        if var_ref is not None:
            raise CodegenError(
                f'"{var_name}" already defined in local scope',
                position
            )

        var_ref = self.module.globals.get(var_name, None)
        if var_ref is not None:
            raise CodegenError(
                f'"{var_name}" already defined in universal scope',
                position
            )
       
        allocation_type = var_type

        var_ref = self._alloca(
            var_name, allocation_type,
            current_block=local_alloca,
            node=node
        )

        self.func_symtab[var_name] = var_ref
        return var_ref
    
    def _codegen_create_initializer(self, node_var, node_init):

        # node_var = variable AST node
        # node_init = initializer AST node
        # var_ref = codegenned var from create_variable

        # start with zero initializers
        if node_init is None:
            if node_var.vartype.is_obj_ptr():
                if isinstance(node_var.vartype.pointee, ir.FunctionType):
                    value = self._codegen(node_var)
                else:
                    value = self._alloca('obj', node_var.vartype.pointee)
                return value

            if node_var.vartype.is_ptr():
                # Null pointer
                _ = self._codegen(
                    Number(
                        node_var.position,
                        0,
                        self.vartypes.u_size
                    )
                )
                value = self.builder.inttoptr(
                    _,
                    node_var.vartype
                )
                return value
                        
            # Zero scalar
            value = self._codegen(
                Number(
                    node_var.position,
                    0,
                    node_var.vartype
                )
            )
            return value

       
        value = self._codegen(node_init)
        return value


    def _codegen_variable_assignment(self, node_var, node_init, var_ref, init_ref, element_count = None):

        # node_var = AST node of variable
        # node_init = AST node of initializer
        # var_ref = codegen from create_variable
        # init_ref = codegen from create initializer

        if isinstance(node_init, ItemList):
            element_count = len(init_ref.initializer.constant)
            array_length = var_ref.type.pointee.elements[1].count

            if element_count>array_length:
                raise CodegenError(
                    f'Array initializer is too long (expected {array_length} elements, got {element_count})',
                    node_init.position
                )
            
            if element_count<array_length:
                print (CodegenWarning(
                    f'Array initializer does not fill entire array; remainder will be zero-filled (array has {array_length} elements; initializer has {element_count})',
                    node_init.position
                ))

                for _ in range(0,array_length-element_count):
                    init_ref.initializer.constant.append(
                        ir.Constant(init_ref.initializer.type.element,
                        None)
                    )
                
                init_ref.initializer.type.count = len(init_ref.initializer.constant)

                element_count = init_ref.initializer.type.count
             
            element_width = (
                init_ref.type.pointee.element.width // self.vartypes._byte_width
            ) * element_count

            # Get the pointer to the data area for the target

            sub_var_ref = self.builder.gep(
                var_ref,
                [
                    self._i32(0),
                    self._i32(1)
                ],
            )

            sub_var_ref = self.builder.bitcast(
                sub_var_ref,
                self.vartypes.u_mem.as_pointer()
            )

            sub_val = self.builder.bitcast(
                init_ref,
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
                f'.{node_var.name}.memcpy.'
            )

            return var_ref

        if var_ref.type.pointee != init_ref.type:
            raise CodegenError(
                f'Type declaration and variable assignment type do not match (expected "{var_ref.type.describe()}", got "{init_ref.type.describe()}")',
                node_var.position)

        if var_ref.type.pointee.signed != init_ref.type.signed:
            raise CodegenError(
                f'Type declaration and variable assignment type have signed/unsigned mismatch (expected "{var_ref.type.describe()}", got "{init_ref.type.describe()}")',
                node_var.position)        

        # Copy tracking

        var_ref.heap_alloc = init_ref.heap_alloc
        var_ref.input_arg = init_ref.input_arg

        if var_ref.heap_alloc:
            var_ref.tracked = True        
        
        if init_ref.do_not_allocate:
            self.func_symtab[node_var.name] = init_ref
            return init_ref
        else:
            self.func_symtab[node_var.name] = var_ref
            self.builder.store(init_ref, var_ref)        
            return var_ref
   
    def _codegen_Var(self, node, local_alloca=False):
        for variable in node.vars:

            value = None

            # if there is no initializer
            if variable.initializer is None:

                # and no vartype
                if variable.vartype is None:

                    # use default vartype
                    variable.vartype = self.vartypes._DEFAULT_TYPE

            # if there is an initializer
            else:
                
                # but no variable vartype
                if variable.vartype is None:                    

                    # get the vartype from the initializer
                    value = self._codegen_create_initializer(
                        variable, variable.initializer
                    )
                    variable.vartype = value.type

            # for some types of values, our var has to be
            # reconfigured to match the operations
            # we should make this a property of the value type

            if isinstance(variable.initializer, ItemList):
                variable.vartype = variable.vartype.pointee

            var = self._codegen_create_variable(variable)

            if value is None:
                value = self._codegen_create_initializer(
                variable, variable.initializer
            )

            # assignment is performed even if the value is "empty"
            # so we can assign zero initializers

            assignment = self._codegen_variable_assignment(
                variable, variable.initializer,
                var, value
            )

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

        if getattr(ptr,'global_constant',False):
            raise CodegenError(
                f'"{lhs.name}" is a constant and cannot be modified',
                lhs.position
            )
        
        is_func = ptr.type.is_func()

        if is_func:
            rhs_name = mangle_call(rhs.name, ptr.type.pointee.pointee.args)
            value = self.module.globals.get(rhs_name)
            if not value:
                raise CodegenError(
                    f'Call to unknown function "{rhs.name}" with signature "{[n.describe() for n in ptr.type.pointee.pointee.args]}" (maybe this call signature is not implemented for this function?)',
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

            if isinstance(rhs, ItemList):
                array_value = self._codegen(rhs)
                ptr = self.builder.load(ptr)
                value=self._codegen_variable_assignment(
                    lhs, rhs, ptr, array_value, 
                )
                return value
            else:
                value = self._codegen(rhs)

        # TODO: write test for this
        
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

    def _codegen_FString(self, node):

        # I'm thinking of making this a special case that is
        # not accessible from conventional codegen calls

        format_string = []
        variable_list = []

        if isinstance(node, FString):
            elements = node.elements
        else:
            elements = [node]

        for n in elements:
            if isinstance(n, String):
                format_string.append(n.val)
            
            elif isinstance(n, Number):
                element = self._codegen(n)
                format_type = element.type.p_fmt
                format_string.append(format_type)       
                variable_list.append(element)
            
            elif isinstance(n, (Variable, ItemList, Unsafe)):
                element = self._get_obj_noload(node, n)
                format_type= element.type.p_fmt

                if format_type == '%B':
                    format_type = '%s'
                    bool_str = Call(
                        node.position,
                        '.object.str.__new__',
                        [n]
                    )

                    var_app = Call(
                        node.position,
                        'c_data',
                        [bool_str]
                    )

                elif format_type == '%s':                    
                    var_app = Call(
                        node.position,
                        'c_data',
                        [n]
                    )

                elif format_type in ('%u', '%i', '%f'):
                    var_app = self.builder.load(element)
                
                else:                    
                    n = self._if_unsafe(
                        n, f' (variable {n.body.name if isinstance(n, Unsafe) else n.name} is potentially raw data)'
                    )

                    format_type = '%s'

                    var_app = Call(
                        node.position,
                        'c_data',
                        [n]
                    )                        
                
                format_string.append(format_type)
                variable_list.append(var_app)
        
        return (format_string, variable_list)