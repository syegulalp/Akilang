from core.errors import CodegenError, CodegenWarning
from core.ast_module import Variable, Call, Number, String
import llvmlite.ir as ir
import re

# pylint: disable=E1101

class Builtins():
    
    def _if_unsafe(self, node):
        if not self.allow_unsafe:
            raise CodegenError('Operation must be enclosed in an "unsafe" block', node.position)
    
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
                 [Number(node.position, sizeof, self.vartypes.u_size)]))

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
        addr2 = self.builder.bitcast(addr, self.vartypes.u_mem.as_pointer()).get_reference()

        call = self._codegen_Call(
            Call(node.position, 'c_free',
                 [Number(node.position, addr2,
            self.vartypes.u_mem.as_pointer())]))        

        return call

    def _codegen_Builtins_c_obj_ref(self, node):
        '''
        Returns a typed pointer to the object.
        '''
        expr = self._get_obj_noload(node)
        s1 = self._alloca('obj_ref', expr.type)
        self.builder.store(expr, s1)
        return s1

    def _codegen_Builtins_c_ptr_math(self, node):

        ptr = self._codegen(node.args[0])
        int_from_ptr = self.builder.ptrtoint(ptr, self.vartypes.u_size)
        amount_to_add = self._codegen(node.args[1])
        # TODO: if this is a signed type,
        # perform runtime test for subtraction
        add_result = self.builder.add(int_from_ptr, amount_to_add)
        add_result = self.builder.inttoptr(add_result, ptr.type)

        return add_result

    def _codegen_Builtins_c_ptr_mod(self, node):
        self._if_unsafe(node)

        ptr = self._codegen(node.args[0])
        value = self._codegen(node.args[1])        
        self.builder.store(value, ptr)
        return ptr

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

        return ir.Constant(self.vartypes.u_size, s2)

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

        return ir.Constant(self.vartypes.u_size, s2)

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
        Returns a raw u_mem pointer to the start of an array object.
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
        bc = self.builder.bitcast(gep, self.vartypes.u_mem.as_pointer()) # pylint: disable=E1111
        return bc

    def _codegen_Builtins_c_ptr(self, node):
        '''
        Returns a u_mem ptr to anything
        '''
        self._if_unsafe(node)
        address_of = self._codegen(node.args[0])
        return self.builder.bitcast(address_of, self.vartypes.u_mem.as_pointer())

    def _codegen_Builtins_c_addr(self, node):
        '''
        Returns an unsigned value that is the address of the object in memory.
        '''
        address_of = self._get_obj_noload(node)
        return self.builder.ptrtoint(address_of, self.vartypes.u_size)

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
                    #if cast_from.type.v_id != 'ptr_str':
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
                if self.vartypes._pointer_bitwidth != cast_to.width:
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
    
    def _codegen_Builtins_out(self, node):
        in_template = re.split(r'([{}])', node.args[0].val)
        
        var_names = []        
        escape = False
        open_br = False

        for n in in_template:
            if n==r'{' and not escape:
                open_br = True
                continue
            if n==r'}' and not escape:
                open_br = False
                continue
            if open_br:
                var_ref = self._varaddr(n,False)
                var_names.append([var_ref.type.p_fmt,n])
                continue
            escape=False            
            if n and n[-1]=='\\':
                escape=True
                n=n[0:-1]
            n = n.replace('%','%%')
            var_names.append([n,None])
        
        format_string = []
        variable_list = []

        for n in var_names:
            format_string.append(n[0])

            if n[1] is None:
                continue

            if n[0] == '%s':
                var_app = Call(
                    node.position,
                    'c_data',
                    [Variable(node.position, n[1])]
                )
            else:
                var_app = Variable(node.position, n[1])

            variable_list.append(var_app)

        str_to_extract = String(node.position, ''.join(format_string))

        convert = Call(
            node.position,
            'c_data',
            [str_to_extract]
        )

        variable_list.insert(0,convert)

        return self._codegen(
            Call(
                node.position,
                'printf',
                variable_list,
                self.vartypes.i32
            )
        )
