from core.llvmlite_custom import _PointerType, MyType
from core.utils.map import Map

import llvmlite.ir as ir
import ctypes
from llvmlite import binding

from enum import Enum


def make_type_as_ptr(my_type):
    def type_as_ptr(addrspace=0):
        t = _PointerType(my_type, addrspace, v_id=my_type.v_id)
        return t

    return type_as_ptr


class AkiObj:
    signed = False
    is_obj = True


class AkiInt(ir.IntType):
    is_obj = False

    _ctype = {
        "u_size": ctypes.c_voidp,
        "u_mem": ctypes.c_uint8,
        True: {
            1: ctypes.c_bool,
            8: ctypes.c_byte,
            16: ctypes.c_short,
            32: ctypes.c_long,
            64: ctypes.c_longlong,
        },
        False: {
            1: ctypes.c_bool,
            8: ctypes.c_ubyte,
            16: ctypes.c_short,
            32: ctypes.c_ulong,
            64: ctypes.c_ulonglong,
        },
    }

    @property
    def c_type(self):
        if self.v_id in self._ctype:
            return self._ctype[self.v_id]
        return self._ctype[self.signed][self.width]


class AkiFloat:
    signed = True
    is_obj = False
    p_fmt = "%f"

    _ctype = {"f16": ctypes.c_float, "f32": ctypes.c_double, "f64": ctypes.c_longdouble}

    @property
    def c_type(self):
        return self._ctype[self.v_id]


class Bool(AkiInt):

    # TODO: bools need to print as 'True','False'

    p_fmt = "%B"

    def __new__(cls):
        instance = super().__new__(cls, 1, False, True)
        instance.__class__ = Bool
        return instance


class SignedInt(AkiInt):
    p_fmt = "%i"

    def __new__(cls, bits, force=True):
        instance = super().__new__(cls, bits, force, True)
        instance.__class__ = SignedInt
        return instance


class UnsignedInt(AkiInt):
    p_fmt = "%u"

    def __new__(cls, bits, force=True):
        instance = super().__new__(cls, bits, force, False)
        instance.__class__ = UnsignedInt
        return instance


class Float32(AkiFloat, ir.FloatType):
    v_id = "f32"
    width = 32

    def __new__(cls):
        instance = super().__new__(cls)
        instance.__class__ = Float32
        return instance


class Float64(AkiFloat, ir.DoubleType):
    v_id = "f64"
    width = 64

    def __new__(cls):
        instance = super().__new__(cls)
        instance.__class__ = Float64
        return instance


class AkiCArray(AkiObj, ir.ArrayType):
    """
    Type for raw C arrays.
    """

    is_obj = False

    def __init__(self, my_type, my_len):
        super().__init__(my_type, my_len)
        self.v_id = "carray_" + my_type.v_id
        self.signed = my_type.signed
        self.as_pointer = make_type_as_ptr(self)


class AkiCustomType:
    def __new__(cls, module, name, types, v_types):
        instance = module.context.get_identified_type(".class." + name)

        # if not issubclass(instance.__class__, AkiObj):
        class _this(AkiObj, instance.__class__):
            pass

        instance.__class__ = _this

        instance.elements = types
        instance.v_types = v_types
        instance.v_id = name
        instance.as_pointer = make_type_as_ptr(instance)

        return instance


class AkiArray(AkiObj, ir.LiteralStructType):
    """
    Type for arrays whose dimensions are defined at compile time.
    """

    del_id = "array"
    del_as_ptr = True

    def __init__(self, vartypes, my_type, elements):

        arr_type = my_type
        for n in reversed(elements):
            arr_type = vartypes.carray(arr_type, n)

        master_type = [vartypes._header, arr_type]

        super().__init__(master_type)

        self.as_pointer = make_type_as_ptr(self)
        self.master_type = master_type
        self.arr_type = my_type

        self.v_id = f"array_{my_type.v_id}"

        set_type_id(vartypes, self)

        # I think we need to have the initializer here

    def new_signature(self):
        return (".object.array.__new__", self.arr_type)

    def post_new_bitcast(self, builder, obj):
        obj = builder.bitcast(obj, self.as_pointer())

        return obj


class AkiHeader(AkiObj, ir.IdentifiedStructType):
    DATA_SIZE = 0
    DATA_PTR = 1
    OBJ_ENUM = 2
    OBJ_REFCOUNT = 3
    OBJ_MALLOC = 4
    HEADER_MALLOC = 5


class AkiBox(AkiObj, ir.IdentifiedStructType):
    v_id = "box"
    is_obj = True
    signed = False
    p_fmt = None


class AkiStr(AkiObj, ir.IdentifiedStructType):
    v_id = "str"
    is_obj = True
    p_fmt = "%s"


class AkiFunc(AkiObj, ir.FunctionType):
    v_id = "func"
    is_obj = True

def set_type_id(vartypes, type_to_check):
    lookup = vartypes._enum_lookup.get(type_to_check.v_id)
    if not lookup:
        vartypes._enum_count +=1
        type_to_check.enum_id = vartypes._enum_count
        vartypes._enum_lookup[type_to_check.v_id] = type_to_check
    else:
        type_to_check.enum_id = lookup.enum_id

_default_platform_module = ir.Module()
_default_platform_vartypes = {}


def generate_vartypes(module=_default_platform_module, bytesize=8):

    # if no module, assume current platform
    # cache a copy of the default platform module
    # for the lifetime of the app

    try:
        return _default_platform_vartypes[module.triple]
    except Exception:
        pass

    # Initialize target data for the module.
    target_data = binding.create_target_data(module.data_layout)

    # Set up pointer size and u_size vartype for target platform.
    _byte_width = ir.PointerType(ir.IntType(bytesize)).get_abi_size(target_data)

    _pointer_width = _byte_width * bytesize

    U_MEM = UnsignedInt(_byte_width)
    U_SIZE = UnsignedInt(_pointer_width)

    _bool = Bool()

    Header = ir.global_context.get_identified_type(".object_header.")
    Header.__class__ = AkiHeader
    Header.elements = (
        # total length of data element in bytes as u64
        U_SIZE,
        # pointer to object data
        U_MEM.as_pointer(),  # generic ptr void
        # object descriptor
        U_SIZE,
        # refcount
        U_SIZE,
        # flag for whether or not pointed-to obj (by way of element 1) is dynamically allocated (bool)
        # default is 0
        _bool,
        # flag for whether or not this obj is dynam. alloc.
        # default is also 0
        _bool,
    )

    Header.packed = True

    # for arrays at compile time, we can encode the dimensions at compile time
    # and any calls will be optimized out to constants anyway
    # need to see if the .initializer property works for runtime

    # create objects dependent on the ABI size

    Box = ir.global_context.get_identified_type(".box.")
    Box.__class__ = AkiBox
    Box.elements = (
        Header,
        # ir.IntType(_byte_width)
    )

    Box.as_pointer = make_type_as_ptr(Box)

    Str = ir.global_context.get_identified_type(".object.str")
    Str.__class__ = AkiStr
    Str.elements = (Header,)
    Str.as_pointer = make_type_as_ptr(Str)

    _vartypes = Map(
        {
            # abstract types
            "int": AkiInt,
            "float": AkiFloat,
            "obj": Header,
            # scalars
            # bitwidths universal across platforms
            "u1": _bool,
            "bool": _bool,
            "i8": SignedInt(8),
            "i16": SignedInt(16),
            "i32": SignedInt(32),
            "i64": SignedInt(64),
            "u8": UnsignedInt(8),
            "u16": UnsignedInt(16),
            "u32": UnsignedInt(32),
            "u64": UnsignedInt(64),
            "f32": Float32(),
            "f64": Float64(),
            # platform-specific scalars
            "u_size": U_SIZE,
            "u_mem": U_MEM,
            "byte": U_MEM,
            # non-singleton, needs instantiation
            "carray": AkiCArray,
            "array": AkiArray,
            # object type, not instantiated
            "str": Str,
            # object type, instantiation by way of builtin
            "box": Box,
            # function type
            "func": AkiFunc,
            # other data
            "_header": Header,
            "_byte_width": _byte_width,
            "_pointer_width": _pointer_width,
            "_arrayclass": AkiArray,
            "_carrayclass": AkiCArray,
            "_strclass": AkiStr,
            "_target_data": target_data,
        }
    )

    # set defaults for functions and variables
    _vartypes._DEFAULT_TYPE = _vartypes.i32
    _vartypes._DEFAULT_RETURN_VALUE = ir.Constant(_vartypes._DEFAULT_TYPE, 0)

    # enumerant for type identifiers
    _enum = {}    

    for _, n in enumerate(_vartypes):
        if not n.startswith("_"):
            _enum[_] = _vartypes[n]
            _vartypes[n].enum_id = _

    _vartypes._enum = _enum
    _vartypes._enum_count = _
    _vartypes._enum_lookup = {}

    _default_platform_vartypes[module.triple] = _vartypes

    return _vartypes
