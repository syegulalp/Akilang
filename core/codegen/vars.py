import llvmlite.ir as ir
from core.errors import CodegenError
from core.ast_module import Variable, Call, ArrayAccessor
from core.mangling import mangle_call
#from core.vartypes import VarTypes, DEFAULT_TYPE
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

    def _codegen_AllocaInstr(self, node):
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
            ptr = self.builder.gep(array, accessor, True, f'{array.name}')
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

    def _codegen_Variable(self, node, noload=False):

        current_node = node
        previous_node = None
        previous = None

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
                
                if isinstance(latest.type.pointee, ArrayClass):

                    latest = self._codegen_ArrayElement(
                        current_node, array_element)
                    current_load = not latest.type.is_obj_ptr()
                
                else:
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
            self.vartypes.u8.as_pointer())

        # Create the string object that points to the constant.

        str_val = ir.GlobalVariable(module, self.vartypes.str, str_name)
        str_val.storage_class = 'private'
        str_val.unnamed_addr = True
        str_val.global_constant = True

        str_val.initializer = self.vartypes.str(
            [ir.Constant(self.vartypes.u64, string_length), spt])

        # Note: If this is being invoked as a standalone
        # expression, we need to create a temp variable
        # so it has something to point to.
        # Otherwise expressions like "Hi there"[1] don't work.

        # local_instance = self.builder.alloca(self.vartypes.str.as_pointer())
        # self.builder.store(str_val, local_instance)

        #local_instance_ptr = self.builder.alloca(local_instance.type)
        #self.builder.store(local_instance, local_instance_ptr)

        #self.last_inline = local_instance
        self.last_inline = str_val
        #print (type(str_val.type))

        return str_val
        #return local_instance_ptr
        #return local_instance

    def _codegen_Var(self, node, local_alloca=False):
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
