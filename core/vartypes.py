import llvmlite.ir as ir

from core.llvmlite_custom import Map, _PointerType, MyType

# Singleton types (these do not require an invocation, they're only created once)


def make_type_as_ptr(type):
    def type_as_ptr(addrspace=0):
        t = _PointerType(type, addrspace, v_id=type.v_id)
        # if  type.underlying_obj() is None:
        #     t.original_obj = type
        # else:
        #     t.original_obj = type.original_obj
        return t

    return type_as_ptr


class Bool(ir.IntType):
    def __new__(cls):
        return super().__new__(cls, 1, False, False)


class SignedInt(ir.IntType):
    def __new__(cls, bits, force=True):
        return super().__new__(cls, bits, force, True)


class UnsignedInt(ir.IntType):
    def __new__(cls, bits, force=True):
        return super().__new__(cls, bits, force, False)


class Float64(ir.DoubleType):
    def __new__(cls):
        t = super().__new__(cls)
        t.signed = True
        t.v_id = 'f64'
        t.width=64
        return t

# Non-singleton types (these require an invocation)


class Array(ir.ArrayType):
    def __new__(cls, type, len):
        t = ir.ArrayType(type, len)
        t.v_id = 'array_' + type.v_id
        t.signed = type.signed
        t.as_pointer = make_type_as_ptr(t)

        return t


ir.IntType.is_obj = False
ir.DoubleType.is_obj = False
ir.ArrayType.is_obj = False


class CustomClass():
    def __new__(cls, name, types, v_types):
        new_class = ir.global_context.get_identified_type('.class.' + name)
        new_class.elements = types
        new_class.v_types = v_types
        new_class.v_id = name
        new_class.signed = False
        new_class.is_obj = True
        new_class.as_pointer = make_type_as_ptr(new_class)

        return new_class


# object types

Ptr = ir.global_context.get_identified_type('.object.ptr')
Ptr.elements = (UnsignedInt(8, True).as_pointer(), )
Ptr.v_id = "ptrobj"
Ptr.is_obj = True
Ptr.signed = False
Ptr.ext_ptr = UnsignedInt(8, True).as_pointer()

# create String type manually, for now

Str = ir.global_context.get_identified_type('.object.str')
Str.elements = (ir.IntType(8).as_pointer(), ir.IntType(32), )
Str.v_id = 'str'
Str.is_obj = True
Str.signed = False
# type signature for external (C-library) stuff
Str.ext_ptr = UnsignedInt(8, True).as_pointer()
Str.as_pointer = make_type_as_ptr(Str)


NoneType = ir.global_context.get_identified_type('.object.none')
NoneType.elements = (ir.IntType(1), )
NoneType.v_id = 'none'
NoneType.is_obj = True
NoneType.signed = False
NoneType.ext_ptr = ir.IntType(8).as_pointer()
# don't know if we need this, placeholder for now

# each runtime creates one Nonetype object
# so when we return that as our default value,
# we're returning a pointer to that single instance

# Object wrapper

Obj = ir.global_context.get_identified_type('.object.base')
Obj.elements = (
    ir.IntType(8),  # object type identifier
    ir.IntType(8).as_pointer()  # pointer to the object data itself
    # eventually, a pointer to a dict obj for properties
)
Obj.v_id = 'obj'
Obj.is_obj = True
Obj.ext_ptr = ir.IntType(8).as_pointer()
# actually ptr to void, not sure this will be used for anything

object_typemap = {0: NoneType, 1: Str}

# object layout:
# element 1 = object type as i8
# element = pointer to object
# object mapping:
# 0 = None
# 1 = str

# when do we use the object wrapper? maybe when we expect an object generically.
# we can return anything. so maybe for toplevel returns from main we wrap in an object?
# default return should be a None, which translates to 0
# when returned from main() we should provide a wrapper and deref that manually
# in the repl, using something in vartypes

# maybe each should include its own deref function, too

VarTypes = Map({
    #singleton
    'u1': Bool(),
    'i8': SignedInt(8),
    'i16': SignedInt(16),
    'i32': SignedInt(32),
    'i64': SignedInt(64),
    'u8': UnsignedInt(8),
    'u16': UnsignedInt(16),
    'u32': UnsignedInt(32),
    'u64': UnsignedInt(64),
    'f64': Float64(),
    'ptr_size': None,
    # ptr_size is set on init

    # non-singleton
    'array': Array,

    # object types
    'str': Str,
    'ptrobj': Ptr,
    'None': NoneType,

    #'any': Any
})

import ctypes

VarTypes.u1.c_type = ctypes.c_bool
VarTypes.u8.c_type = ctypes.c_ubyte
VarTypes.i16.c_type = ctypes.c_short
VarTypes.u16.c_type = ctypes.c_short
VarTypes.i32.c_type = ctypes.c_long
VarTypes.i64.c_type = ctypes.c_longlong
VarTypes.u32.c_type = ctypes.c_ulong
VarTypes.u64.c_type = ctypes.c_ulonglong
VarTypes.f64.c_type = ctypes.c_longdouble

# add these types in manually, since they just shadow existing ones

VarTypes['bool'] = VarTypes.u1
VarTypes['byte'] = VarTypes.u8
VarTypes['func'] = ir.FunctionType



# eventually this will be set to None
# when we support object types as the default

DEFAULT_TYPE = VarTypes.i32
DEFAULT_RETURN_VALUE = ir.Constant(VarTypes.i32, 0)

dunder_methods = [f'__{n}__' for n in ['len']]

#print(dunder_methods)