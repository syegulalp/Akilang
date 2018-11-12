from core.errors import CodegenError
from core.ast_module import VariableType, Call
import llvmlite.ir as ir

# pylint: disable=E1101

class Builtins_boxes():
    def _box_check(self, node):
        '''
        Determine if a given variable is a container.
        '''

        box_ptr = self._get_obj_noload(node, arg=0)

        if type(box_ptr) == ir.AllocaInstr:
            box_ptr = self.builder.load(box_ptr)

        if not box_ptr.type == self.vartypes.obj.as_pointer():
            raise CodegenError(
                "Not a boxed value",
                node.args[0].position
            )

        return box_ptr

    def _codegen_Builtins_unbox(self, node):
        '''
        Extracts an object of a certain expected type from a container.
        If the wrong type is found, a supplied object of the correct type
        can be substituted.
        '''

        # TODO: add object tracking along all paths
        # TODO: add box types for user-defined classes, too

        self._check_arg_length(node, 3)
        box_ptr = self._box_check(node)
        type_to_unwrap = node.args[1]

        if not isinstance(type_to_unwrap, VariableType):
            raise CodegenError(
                f'Parameter must be a type descriptor',
                node.args[1].position
            )

        # Generate the substitute data
        value_to_substitute = self._codegen(node.args[2])

        if value_to_substitute.type != type_to_unwrap.vartype:
            raise CodegenError(
                f'Substitute value must be the same type as the expected type',
                node.args[2].position
            )

        if type_to_unwrap.vartype.is_ptr():
            enum_id = type_to_unwrap.vartype.pointee.enum_id
        else:
            enum_id = type_to_unwrap.vartype.enum_id

        # Get pointer to object to unwrap

        ptr_to_unwrap = self.builder.gep(
            box_ptr,
            [
                self._i32(0),
                self._i32(0),
                self._i32(
                    self.vartypes._header.OBJ_POINTER
                )
            ]
        )

        unwrap = self.builder.load(ptr_to_unwrap)

        # Get type enum to expect

        type_to_expect = self.builder.gep(
            box_ptr,
            [
                self._i32(0),
                self._i32(0),
                self._i32(
                    self.vartypes._header.OBJ_ENUM
                )
            ]
        )

        # Allocate space for ptr to return value

        return_ptr = self.builder.alloca(
            type_to_unwrap.vartype
        )

        # Check that the expected type is the same

        pred = self.builder.icmp_unsigned(
            '==',
            self.builder.load(type_to_expect),
            ir.Constant(
                self.vartypes.u_size,
                enum_id
            )
        )

        with self.builder.if_else(pred) as (then, otherwise):
            with then:

                # This is the default pointer when all is well.

                bitcast = self.builder.bitcast(
                    unwrap,
                    type_to_unwrap.vartype.as_pointer()
                )

                self.builder.store(
                    self.builder.load(bitcast),
                    return_ptr
                )

            with otherwise:

                # This is the pointer to the new object.
                data_malloc = self._codegen(
                    Call(
                        node.position,
                        'c_alloc',
                        [ir.Constant(
                            self.vartypes.u_size,
                            self._obj_size(value_to_substitute)
                        )]
                    )
                )

                # bitcast to the appropriate pointer type
                data_ptr = self.builder.bitcast(
                    data_malloc,
                    value_to_substitute.type.as_pointer()
                )

                # store the data in our malloc'd space
                self.builder.store(
                    value_to_substitute,
                    data_ptr
                )

                # store pointer to data as our return item

                bitcast = self.builder.bitcast(
                    data_malloc,
                    type_to_unwrap.vartype.as_pointer()
                )

                self.builder.store(
                    self.builder.load(bitcast),
                    return_ptr
                )

        bitcast_ptr = self.builder.bitcast(
            return_ptr,
            type_to_unwrap.vartype.as_pointer()
        )

        return self.builder.load(bitcast_ptr)

    def _codegen_Builtins_objtype(self, node):
        '''
        Retrieves the type of an object inside a container.
        '''

        self._check_arg_length(node)
        box_ptr = self._box_check(node)

        box_type = self.builder.gep(
            box_ptr,
            [
                self._i32(0),
                self._i32(0),
                self._i32(
                    self.vartypes._header.OBJ_ENUM
                )
            ]
        )

        return self.builder.load(box_type)

    def _codegen_Builtins_box(self, node):
        '''
        Place a variable inside a container.
        '''

        self._check_arg_length(node)

        # malloc space for a copy of the data
        data_to_convert = self._codegen(node.args[0])

        if data_to_convert.type.is_ptr():
            enum_id = data_to_convert.type.pointee.enum_id
        else:
            enum_id = data_to_convert.type.enum_id

        data_malloc = self._codegen(
            Call(node.position, 'c_alloc',
                 [ir.Constant(self.vartypes.u_size,
                              self._obj_size(data_to_convert))]
                 )
        )

        # bitcast to the appropriate pointer type
        data_ptr = self.builder.bitcast(
            data_malloc,
            data_to_convert.type.as_pointer()
        )

        # store the data in our malloc'd space
        self.builder.store(
            data_to_convert,
            data_ptr
        )

        # Allocate space for the object wrapper
        obj_alloc_ptr = self._codegen(
            Call(node.position, 'c_obj_alloc',
                 [VariableType(node.position, self.vartypes.obj)]
                 )
        )

        # Get object data size
        data_length = self._obj_size(data_to_convert)

        # load object from its pointer so we can GEP it
        obj_alloc = self.builder.load(obj_alloc_ptr)

        svh = self.vartypes._header

        for n in (
            (False, svh.DATA_SIZE, self.vartypes.u_size, data_length),
            (True, svh.OBJ_POINTER, self.vartypes.u_mem.as_pointer(), data_malloc),
            (False, svh.OBJ_ENUM, self.vartypes.u_size, enum_id),
            (False, svh.OBJ_MALLOC, self.vartypes.bool, True),
            (False, svh.HEADER_MALLOC, self.vartypes.bool, True),
        ):

            n_ptr = self.builder.gep(
                obj_alloc,
                [
                    self._i32(0),
                    self._i32(0),
                    self._i32(n[1])
                ]
            )

            if n[0]:
                value = n[3]
            else:
                value = ir.Constant(n[2], n[3])

            self.builder.store(
                value,
                n_ptr
            )

        return obj_alloc

    def _codegen_Builtins_type(self, node):
        self._check_arg_length(node)
        type_obj = node.args[0]

        if isinstance(type_obj, VariableType):
            type_obj = type_obj.vartype
        else:
            type_obj = self._codegen(type_obj).type

        if type_obj in (
                ir.FunctionType,
                self.vartypes.carray,
                self.vartypes.array
            ):            
            enum_id = type_obj.enum_id

        elif type_obj.is_ptr():
            enum_id = type_obj.pointee.enum_id
        
        else:
            # pathological case
            enum_id = type_obj.enum_id

        enum_val = ir.Constant(
            self.vartypes.u_size,
            enum_id
        )

        return enum_val