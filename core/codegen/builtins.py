from core.errors import (
    CodegenError,
    CodegenWarning,
    ParameterFormatError,
    AkiSyntaxError,
)
from core.ast_module import (
    Variable,
    Call,
    Number,
    String,
    FString,
    ItemList,
    Binary,
    Unsafe,
    VariableType,
    If,
    Expr
)

COMMON_ARGS = (Expr,)

import llvmlite.ir as ir
from core.tokens import Ops
from core.vartypes import set_type_id

# pylint: disable=E1101


class Builtins:
    def _if_unsafe(self, node, explanation=""):
        if isinstance(node, Unsafe):
            return node.body
        if not self.allow_unsafe:
            raise AkiSyntaxError(
                f'Operation must be enclosed in an "unsafe" block{explanation}',
                node.position,
            )
        return node

    def _check_arg_length(self, node, min_args=1, max_args=1):
        argcount = len(node.args)
        pos = node.args[argcount - 1].position if argcount > 0 else node.position
        
        if argcount < min_args:
            raise AkiSyntaxError(
                f"Too few arguments (expected {min_args}, got {argcount})", pos
            )

        if max_args and len(node.args) > max_args:
            raise AkiSyntaxError(
                f"Too many arguments (expected {max_args}, got {argcount})",
                pos
            )

    def _check_arg_types(self, node, types, ext_types=None):
        for _, n in enumerate(node.args):
            if _>len(types)-1:
                t=ext_types
            else:
                t = types[_]
            
            if type(n).__base__ not in t and type(n) not in t:
                raise AkiSyntaxError(
                    f'Argument {_} is the wrong type (expected one of "{[x.description() for x in t]}", got "{type(n).description()}"',
                    n.position
                )

    def _check_pointer(self, obj, node):
        """
        Determines if a given item is a pointer or object.
        """
        if not obj.type.is_pointer:
            raise CodegenError(
                "Parameter must be a pointer or object", node.args[0].position
            )

    def _get_obj_noload(self, node, arg=None, ptr_check=True):
        """
        Returns a pointer (or variable reference) to a codegenned object,
        but don't load from the pointer.
        This is used when we want to work with the variable reference,
        for instance to get object tracking data.
        """
        if not arg:
            arg = node.args[0]

        if isinstance(arg, Variable):
            codegen = self._codegen_Variable(arg, noload=True)
        else:
            codegen = self._codegen(arg)

        if ptr_check:
            self._check_pointer(codegen, node)

        return codegen

    def _extract_data_ptr(self, convert_from, node):
        """
        Follows the generic u_mem data pointer
        in an object header to the object data
        """

        gep = self.builder.gep(
            convert_from,
            [
                # object instance
                self._i32(0),
                # header
                self._i32(0),
                # ptr to mem
                self._i32(self.vartypes._header.DATA_PTR),
            ],
        )

        gep = self.builder.load(gep)
        gep.type.p_fmt = None
        return gep

    def _extract_ptr(self, convert_from, node):
        """
        Returns a generic u_mem pointer
        to the first element of an object
        """
        gep = self.builder.gep(convert_from, [self._i32(0)])

        bc = self.builder.bitcast(
            gep, self.vartypes.u_mem.as_pointer(), ".extract.ptr"
        )  # pylint: disable=E1111

        return bc

    def _extract_array(self, convert_from, node):
        """
        Returns a generic u_mem pointer
        to the start of an object's data body
        """
        gep = self.builder.gep(
            convert_from,
            [
                # object instance
                self._i32(0),
                # ptr to body
                self._i32(1),
            ],
        )

        bc = self.builder.bitcast(
            gep, self.vartypes.u_mem.as_pointer(), ".extract.array"
        )  # pylint: disable=E1111

        return bc

    def _codegen_Builtins_c_obj_alloc(self, node):

        # TODO: test for allocation of user-defined classes

        # In time we will phase this out and replace it with
        # all generic calls to <type>.__new__()

        self._check_arg_length(node)
        self._check_arg_types(node, ((VariableType,),))

        vt = node.args[0]
        v1 = vt.vartype

        if v1 is None:
            v1 = self.class_symtab.get(vt.name, None)

        if v1 is None:
            raise CodegenError(
                f'Unknown type or class "{vt.name}"', node.args[0].position
            )

        if v1.is_pointer:
            v1 = v1.pointee

        sizeof = v1.get_abi_size(self.vartypes._target_data)

        call = self._codegen_Call(
            Call(
                node.position,
                "c_alloc",
                [Number(node.position, sizeof, self.vartypes.u_size)],
            )
        )

        b1 = self.builder.bitcast(call, v1.as_pointer())  # pylint: disable=E1111

        if v1.is_obj:
            b2 = self.builder.alloca(b1.type)
            self.builder.store(b1, b2)
            self._set_tracking(b2)
        else:
            b2 = b1
            self._set_tracking(b2, True, None, None)

        return b2

    def _codegen_Builtins_c_obj_free(self, node):
        """
        Deallocates memory for an object created with c_obj_alloc.
        """

        self._check_arg_length(node)
        self._check_arg_types(node, (COMMON_ARGS,))

        expr = self._get_obj_noload(node)

        if not expr.tracked:
            raise CodegenError(
                f'"{node.args[0].name}" is not an allocated object',
                node.args[0].position,
            )

        # Mark the variable in question as untracked
        self._set_tracking(expr, None, None, False)

        addr = self.builder.load(expr)
        addr2 = self.builder.bitcast(addr, self.vartypes.u_mem.as_pointer())

        # TODO: replace with call to
        # .object.obj.__del__
        # this will also destroy any
        # enclosed object if it needs it

        # ? bitcast to obj wrapper?
        # or just get obj header ptr and use that?

        call = self._codegen_Call(Call(node.position, "c_free", [addr2]))

        # TODO: zero after free, automatically

        return call

    def _codegen_Builtins_c_obj_ref(self, node):
        """
        Returns a typed pointer to the object.
        """

        self._check_arg_length(node)
        self._check_arg_types(node, (COMMON_ARGS,))

        expr = self._get_obj_noload(node)
        s1 = self._alloca("obj_ref", expr.type)
        self.builder.store(expr, s1)
        return s1

    def _codegen_Builtins_c_ptr_math(self, node):

        self._check_arg_length(node, 2, 2)
        self._check_arg_types(node, (COMMON_ARGS, COMMON_ARGS))

        ptr = self._codegen(node.args[0])
        int_from_ptr = self.builder.ptrtoint(ptr, self.vartypes.u_size)
        amount_to_add = self._codegen(node.args[1])

        # TODO: ints only!
        # and upconvert if needed?

        # TODO: if this is a signed type,
        # perform runtime test for subtraction
        add_result = self.builder.add(int_from_ptr, amount_to_add)
        add_result = self.builder.inttoptr(add_result, ptr.type)

        return add_result

    def _codegen_Builtins_c_ptr_mod(self, node):

        node = self._if_unsafe(node)
        self._check_arg_length(node, 2, 2)
        self._check_arg_types(node, (COMMON_ARGS, COMMON_ARGS))

        ptr = self._codegen(node.args[0])
        value = self._codegen(node.args[1])
        self.builder.store(value, ptr)

        # XXX: I'm assuming a modified pointer object
        # cannot be automatically disposed b/c
        # we edit it manually

        self._set_tracking(ptr, None, None, False)
        # ptr.tracked = False

        return ptr

    def _codegen_Builtins_c_gep(self, node):
        self._check_arg_length(node, 1, None)
        self._check_arg_types(node, (COMMON_ARGS,), COMMON_ARGS)
        obj = self._codegen(node.args[0])

        if (len(node.args)) < 2:
            return self.builder.load(obj)

        index = [self._i32(0)]

        for n in range(1, len(node.args)):
            index.append(self._codegen(node.args[n]))

        try:
            gep = self.builder.gep(obj, index)
        except IndexError:
            raise CodegenError(f'Index "{index}" is not valid', node.position)
        return gep

    def _codegen_Builtins_c_ptr_int(self, node):
        self._check_arg_length(node)
        ptr = self._codegen(node.args[0])
        self._check_arg_types(node, (COMMON_ARGS,))
        int_val = self.builder.ptrtoint(ptr, self.vartypes.u_size)
        return int_val

    def _codegen_Builtins_c_size(self, node):
        """
        Returns the size of the object's descriptor in bytes.
        For a string, this is NOT the size of the
        underlying string, but the size of the *structure*
        that describes a string.
        """
        self._check_arg_length(node)
        self._check_arg_types(node, (COMMON_ARGS,))
        expr = self._codegen(node.args[0])

        if expr.type.is_obj_ptr():
            s1 = expr.type.pointee
        else:
            s1 = expr.type

        s2 = self._obj_size_type(s1)

        return ir.Constant(self.vartypes.u_size, s2)

    def _codegen_Builtins_c_data(self, node):
        """
        Returns the underlying C-style data element
        for an object with a pointer to the data.
        """

        self._check_arg_length(node)
        self._check_arg_types(node, (COMMON_ARGS+(String,),))

        convert_from = self._codegen(node.args[0])

        if isinstance(convert_from.type.pointee, self.vartypes._strclass):
            return self._extract_data_ptr(convert_from, node)

        elif isinstance(convert_from.type.pointee, self.vartypes._carrayclass):
            return self._extract_ptr(convert_from, node)

        elif isinstance(convert_from.type.pointee, self.vartypes._arrayclass):
            return self._extract_array(convert_from, node)

        else:
            raise CodegenError(f"Error extracting c_data pointer", node.position)

    def _codegen_Builtins_c_ptr(self, node):
        '''
        Returns a typed pointer to any object.
        '''
        self._check_arg_length(node)
        self._check_arg_types(node, (COMMON_ARGS,))

        a0 = self._get_obj_noload(node, ptr_check=False)
        if not isinstance(a0, (ir.LoadInstr, ir.AllocaInstr)):
            raise CodegenError(
                f'Argument must be a variable or expression returning a variable',
                node.args[0].position
            )

        a2 = self._extract_operand(a0)
        return a2

    
    def _codegen_Builtins_c_ptr_mem(self, node):
        """
        Returns a u_mem ptr to anything
        """

        #node = self._if_unsafe(node)
        self._check_arg_length(node, 1, 2)
        self._check_arg_types(node, (COMMON_ARGS,), COMMON_ARGS)
        address_of = self._codegen(node.args[0])

        # if len(node.args) > 1:
        #     use_type = self._codegen(node.args[1], False)
        # else:

        use_type = self.vartypes.u_mem

        return self.builder.bitcast(address_of, use_type.as_pointer())

    def _codegen_Builtins_c_addr(self, node):
        """
        Returns an unsigned value that is the address of the object in memory.
        """

        self._check_arg_length(node)
        self._check_arg_types(node, [COMMON_ARGS])

        address_of = self._get_obj_noload(node)
        return self.builder.ptrtoint(address_of, self.vartypes.u_size)

        # perhaps we should also have a way to cast
        # c_addr as a pointer to a specific type (the reverse of this)

    def _codegen_Builtins_c_deref(self, node):
        """
        Dereferences a pointer to a primitive, like an int.
        """

        self._check_arg_length(node)
        self._check_arg_types(node, [COMMON_ARGS])

        ptr = self._get_obj_noload(node)
        ptr2 = self.builder.load(ptr)

        if hasattr(ptr2.type, "pointee"):
            ptr2 = self.builder.load(ptr2)

        if hasattr(ptr2.type, "pointee") and not self._if_unsafe(node):
            raise CodegenError(
                f'"{node.args[0].name}" is not a reference to a scalar (use "c_obj_deref" for references to objects instead of scalars, or use "unsafe" to dereference regardless of type)',
                node.args[0].position,
            )

        # XXX: self.builder.load clobbers with core._llvmlite_custom._IntType
        return ptr2

    def _codegen_Builtins_c_ref(self, node):
        """
        Returns a typed pointer to a primitive, like an int.
        """

        self._check_arg_length(node)
        self._check_arg_types(node, [COMMON_ARGS])

        expr = self._get_obj_noload(node)

        if expr.type.is_obj_ptr():
            raise CodegenError(
                f'"{node.args[0].name}" is not a scalar (use "c_obj_ref" for references to objects instead of scalars)',
                node.args[0].position,
            )

        return expr

    def _codegen_Builtins_c_obj_deref(self, node):
        """
        Dereferences a pointer (itself passed as a pointer)
        and returns the object at the memory location.
        """

        self._check_arg_length(node)
        self._check_arg_types(node, [COMMON_ARGS, COMMON_ARGS])

        ptr = self._codegen(node.args[0])
        ptr2 = self.builder.load(ptr)
        self._check_pointer(ptr2, node)
        ptr3 = self.builder.load(ptr2)
        return ptr3

    def _codegen_Builtins_call(self, node):
        self._check_arg_length(node, 1, None)
        self._check_arg_types(node, [[String]], COMMON_ARGS)
        func_name = node.args[0]
        return self._codegen(Call(node.position, func_name.val, node.args[1:]))

    def _codegen_Builtins_cast(self, node):
        """
        Cast one data type as another, such as a pointer to a u64,
        or an i8 to a u32.
        Ignores signing.
        Will truncate bitwidths.
        """

        self._check_arg_length(node, 2, 2)
        self._check_arg_types(node, [COMMON_ARGS, [VariableType]])
        
        cast_from = self._codegen(node.args[0])
        cast_to = self._codegen(node.args[1], False)

        cast_exception = CodegenError(
            f'Casting from type "{cast_from.type.describe()}" to type "{cast_to.describe()}" is not supported',
            node.args[0].position,
        )

        while True:

            # If we're casting FROM a pointer...

            if cast_from.type.is_pointer:

                # it can't be an object pointer (for now)
                if cast_from.type.is_obj_ptr() and not self._if_unsafe(node):
                    raise cast_exception

                # but it can be cast to another pointer
                # as long as it's not an object
                if cast_to.is_pointer:
                    if cast_to.is_obj_ptr() and not self._if_unsafe(node):
                        raise cast_exception
                    op = self.builder.bitcast
                    break

                # and it can't be anything other than an int
                if not isinstance(cast_to, ir.IntType):
                    raise cast_exception

                # and it has to be the same bitwidth
                if self.vartypes._pointer_width != cast_to.width:
                    raise cast_exception

                op = self.builder.ptrtoint
                break

            # If we're casting TO a pointer ...

            if cast_to.is_pointer:

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
                # cast_exception.msg += ' (data would be truncated)'
                # raise cast_exception

            raise cast_exception

        result = op(cast_from, cast_to)
        result.type = cast_to
        return result

    def _codegen_Builtins_convert(self, node):
        """
        Converts data between primitive value types, such as i8 to i32.
        Checks for signing and bitwidth.
        Conversions from or to pointers are not supported here.
        """

        self._check_arg_length(node, 2, 2)
        self._check_arg_types(node, [COMMON_ARGS, [VariableType]])

        convert_from = self._codegen(node.args[0])
        convert_to = self._codegen(node.args[1], False)

        convert_exception = CodegenError(
            f'Converting from type "{convert_from.type.describe()}" to type "{convert_to.describe()}" is not supported',
            node.args[0].position,
        )

        while True:

            # Conversions from/to an object are not allowed

            if convert_from.type.is_obj_ptr() or convert_to.is_obj_ptr():
                explanation = (
                    f"\n(Converting from/to object types will be added later.)"
                )
                convert_exception.msg += explanation
                raise convert_exception

            # Convert from/to a pointer is not allowed

            if convert_from.type.is_pointer or convert_to.is_pointer:
                convert_exception.msg += '\n(Converting from or to pointers is not allowed; use "cast" instead)'
                raise convert_exception

            # Convert from float to int is OK, but warn

            if isinstance(convert_from.type, ir.DoubleType):

                if not isinstance(convert_to, ir.IntType):
                    raise convert_exception

                CodegenWarning(
                    f'Float to integer conversions ("{convert_from.type.describe()}" to "{convert_to.describe()}") are inherently imprecise',
                    node.args[0].position,
                ).print(self)

                if convert_from.type.signed:
                    op = self.builder.fptosi
                else:
                    op = self.builder.fptoui
                break

            # Convert from ints

            if isinstance(convert_from.type, ir.IntType):

                # int to float

                if isinstance(convert_to, ir.DoubleType):

                    CodegenWarning(
                        f'Integer to float conversions ("{convert_from.type.describe()}" to "{convert_to.describe()}") are inherently imprecise',
                        node.args[0].position,
                    ).print(self)

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
                            node.args[0].position,
                        )

                    # Don't allow converting to a smaller bitwidth

                    if convert_from.type.width > convert_to.width:
                        raise CodegenError(
                            f'Type "{convert_from.type.describe()}" cannot be converted to type "{convert_to.describe()}" without possible truncation',
                            node.args[0].position,
                        )

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

    def _codegen_Builtins_print(self, node):

        self._check_arg_length(node, 1, None)
        self._check_arg_types(node, [COMMON_ARGS], COMMON_ARGS)

        format_string = []
        variable_list = []

        spacer = ""
        separator = "\n"

        # This is a crude, hacky way to implement varargs and kwargs,
        # and it only works on builtins.
        # Eventually I'm going to find a better way to do this,
        # once we have the ability to box and unbox types.

        # At one point I mulled the idea of custom-codegenning
        # each function call as a way to accommodate variable length
        # function signatures, but that still left me without any
        # good way to expose the varargs functionality to the underlying
        # code without some kind of type boxing mechanism

        for n1 in reversed(node.args):
            n = n1

            if isinstance(n, Binary) and n.op != Ops.ASSIGN:
                break

            if not isinstance(n, Binary):
                break

            node.args.pop()

            try:

                if not isinstance(n.lhs, Variable):
                    raise ParameterFormatError
                if n.op != "=":
                    raise ParameterFormatError

                if n.lhs.name == "end":
                    if not isinstance(n.rhs, String):
                        raise ParameterFormatError
                    separator = n.rhs.val

                if n.lhs.name == "sep":
                    if not isinstance(n.rhs, String):
                        raise ParameterFormatError
                    spacer = n.rhs.val

            except ParameterFormatError:
                raise CodegenError(
                    f"Parameter must follow the format \"<name>='value'\"", n.position
                )

        for arg in node.args:

            format_string.append(spacer)

            if isinstance(arg, String):
                arg.val = arg.val.replace(r"%", r"%%")

            if not isinstance(arg, FString):
                arg = FString(arg.position, [arg])

            new_format_string, new_variable_list = self._codegen_FString(arg)

            format_string += new_format_string
            variable_list += new_variable_list

            spacer = " "

        format_string.append(separator)

        str_to_extract = String(self.vartypes, node.position, "".join(format_string))

        convert = Call(node.position, "c_data", [str_to_extract])

        final_vars = [convert] + variable_list

        return self._codegen(
            Call(node.position, "printf", final_vars, self.vartypes.i32)
        )

        # TODO: use snprintf to create the final string in memory,
        # then call print on it and return ptr to snprintf'd raw string
