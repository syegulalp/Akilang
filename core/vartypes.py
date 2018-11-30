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
        'u_size': ctypes.c_voidp,
        'u_mem': ctypes.c_uint8,
        True: {
            1: ctypes.c_bool,
            8: ctypes.c_byte,
            16: ctypes.c_short,
            32: ctypes.c_long,
            64: ctypes.c_longlong
        },
        False: {
            1: ctypes.c_bool,
            8: ctypes.c_ubyte,
            16: ctypes.c_short,
            32: ctypes.c_ulong,
            64: ctypes.c_ulonglong
        }
    }

    @property
    def c_type(self):
        if self.v_id in self._ctype:
            return self._ctype[self.v_id]
        return self._ctype[self.signed][self.width]    


class AkiFloat:
    signed=True
    is_obj=False
    p_fmt = '%f'
    
    _ctype = {
        'f16':ctypes.c_float,
        'f32':ctypes.c_double,
        'f64':ctypes.c_longdouble
    }

    @property
    def c_type(self):
        return self._ctype[self.v_id]


class Bool(AkiInt):

    # TODO: bools need to print as 'True','False'

    p_fmt = '%B'

    def __new__(cls):
        instance = super().__new__(cls, 1, False, True)
        instance.__class__ = Bool
        return instance

class SignedInt(AkiInt):
    p_fmt = '%i'

    def __new__(cls, bits, force=True):
        instance= super().__new__(cls, bits, force, True)
        instance.__class__ = SignedInt
        return instance


class UnsignedInt(AkiInt):
    p_fmt = '%u'

    def __new__(cls, bits, force=True):
        instance= super().__new__(cls, bits, force, False)
        instance.__class__ = UnsignedInt
        return instance


class Float32(AkiFloat, ir.FloatType):
    v_id = 'f32'
    width=32

    def __new__(cls):
        instance = super().__new__(cls)
        instance.__class__ = Float32
        return instance


class Float64(AkiFloat, ir.DoubleType):
    v_id = 'f64'
    width=64

    def __new__(cls):
        instance = super().__new__(cls)
        instance.__class__ =Float64
        return instance


class AkiCArray(AkiObj, ir.ArrayType):
    '''
    Type for raw C arrays.
    '''
    is_obj = False

    def __init__(self, my_type, my_len):
        super().__init__(my_type, my_len)
        self.v_id = 'array_' + my_type.v_id
        self.signed = my_type.signed
        self.as_pointer = make_type_as_ptr(self)


class AkiCustomType:
    def __new__(cls, module, name, types, v_types):
        instance = module.context.get_identified_type('.class.' + name)
        
        #if not issubclass(instance.__class__, AkiObj):
        class _this(AkiObj, instance.__class__):
            pass
        instance.__class__ = _this

        instance.elements = types
        instance.v_types = v_types
        instance.v_id = name
        instance.as_pointer = make_type_as_ptr(instance)        

        return instance


class AkiArray(AkiObj, ir.LiteralStructType):
    '''
    Type for arrays whose dimensions are defined at compile time.
    '''

    def __init__(self, my_type, elements):

        arr_type = my_type
        for n in reversed(elements):
            arr_type = VarTypes._carray(arr_type, n)

        master_type = [
            VarTypes._header,
            arr_type
        ]

        super().__init__(
            master_type
        )

        self.v_id = f'array_{my_type.v_id}'
        self.del_id = 'array'
        self.del_as_ptr = True
        self.as_pointer = make_type_as_ptr(self)
        self.master_type = master_type
        self.arr_type = my_type

        # I think we need to have the initializer here

    def new_signature(self):
        return (
            '.object.array.__new__',
            self.arr_type
        )

    def post_new_bitcast(self, builder, obj):
        obj = builder.bitcast(
            obj,
            self.as_pointer()
        )

        return obj

class AkiHeader(AkiObj, ir.IdentifiedStructType):
    pass

class AkiBox(AkiObj, ir.IdentifiedStructType):
    v_id = 'box'
    is_obj = True
    signed = False
    p_fmt = None

class AkiStr(AkiObj, ir.IdentifiedStructType):
    v_id='str'
    is_obj=True
    p_fmt = '%s'


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

    # Set up pointer size and u_size vartype for current hardware.
    _byte_width = (
        ir.PointerType(ir.IntType(bytesize)).get_abi_size(target_data)
    )

    _pointer_width = _byte_width * bytesize

    U_MEM = UnsignedInt(_byte_width)
    U_SIZE = UnsignedInt(_pointer_width)

    Header = ir.global_context.get_identified_type('.object_header.')
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
        ir.IntType(1),

        # flag for whether or not this obj is dynam. alloc.
        # default is also 0
        ir.IntType(1),
    )

    Header.packed = True

    Header.DATA_SIZE = 0
    Header.DATA_PTR = 1
    Header.OBJ_ENUM = 2
    Header.OBJ_REFCOUNT = 3
    Header.OBJ_MALLOC = 4
    Header.HEADER_MALLOC = 5

    # for arrays at compile time, we can encode the dimensions at compile time
    # and any calls will be optimized out to constants anyway
    # need to see if the .initializer property works for runtime

    # Box 
    
    Box = ir.global_context.get_identified_type('.box.')
    Box.__class__ = AkiBox
    Box.elements = (Header,
                    # ir.IntType(_byte_width)
                    )

    Box.as_pointer = make_type_as_ptr(Box)

    # how this works:
    # Header element 2 contains the enum descriptor.
    # The Obj itself is allocated with enough space to include the object,
    # starting at element 0,1.
    # Total size of that element is stored in header 0.
    # To extract, we either produce a properly typed pointer,
    # or we allocate and copy out.

    # We need to keep a running list of all types used in the current module
    # for these kinds of operations.
    # Maybe by way of
    # unwrap (expect type) = generate unwrapper
    # keep a running list of unwraps

    # Result type

    # Result = ir.global_context.get_identified_type('.result.')
    # Result.elements = (Header,
    #                    # OK or err? default is OK
    #                    ir.IntType(1),
    #                    # if false
    #                    ir.IntType(_byte_width).as_pointer(),
    #                    # if true
    #                    ir.IntType(_byte_width).as_pointer(),
    #                    )
    # Result.v_id = 'result'
    # Result.is_obj = True
    # Result.signed = False

    # results should be heap-allocated by default, I think

    # when we compile,
    # we bitcast the ptr to #1 to the appropriate object type
    # based on what we expect
    # for instance, if we have a function that returns an i64
    # but can throw an exception,
    # then any results returned from that have element 1 bitcast
    # as a pointer to an i64 somewhere (malloc'd)
    # it may be possible to return the data directly inside the structure
    # depending on how funky we want to get...
    # basically, we generate the result structure on the fly each time?

    # create objects dependent on the ABI size

    Str = ir.global_context.get_identified_type('.object.str')
    Str.__class__ = AkiStr
    Str.elements = (Header,)
    Str.as_pointer = make_type_as_ptr(Str)

    # Err = ir.global_context.get_identified_type('.err.')
    # Err.elements = (Header,
    #                 Str
    #                 )
    # Err.is_obj = True
    # Err.signed = False

    _vartypes = Map({

        # abstract
        'int': AkiInt,
        'float': AkiFloat,
        'obj': Header,

        # singleton
        'u1': Bool(),
        'i8': SignedInt(8),
        'i16': SignedInt(16),
        'i32': SignedInt(32),
        'i64': SignedInt(64),
        'u8': UnsignedInt(8),
        'u16': UnsignedInt(16),
        'u32': UnsignedInt(32),
        'u64': UnsignedInt(64),
        'f32': Float32(),
        'f64': Float64(),

        'u_size': UnsignedInt(_pointer_width),
        'u_mem': UnsignedInt(_byte_width),

        # non-singleton, needs instantiation
        'carray': AkiCArray,
        'array': AkiArray,
       
        # object type, not instantiated
        'str': Str,

        # object type, instantiation by way of builtin
        'box': Box,

        # function type
        'func': ir.FunctionType,

    })

    # add these types in manually, since they just shadow existing ones
    _vartypes['bool'] = _vartypes.u1
    _vartypes['byte'] = _vartypes.u8

    _vartypes._header = Header

    # set platform-dependent sizes
    _vartypes._byte_width = _byte_width
    _vartypes._pointer_width = _pointer_width

    # TODO: I think we can just refer to them directly
    _vartypes._arrayclass = AkiArray
    _vartypes._carray = AkiCArray
    _vartypes._str = type(Str)

    _vartypes.func.is_obj = True

    # set defaults for functions and variables
    _vartypes._DEFAULT_TYPE = _vartypes.i32
    _vartypes._DEFAULT_RETURN_VALUE = ir.Constant(_vartypes.i32, 0)

    # set the target data reference
    _vartypes._target_data = target_data

    # enumerant for type identifiers
    _enum = {}
    _enum_lookup = {}

    for _, n in enumerate(_vartypes):
        if not n.startswith('_'):
            _enum[_] = _vartypes[n]
            _vartypes[n].enum_id = _

    _ += 1
    _vartypes._arrayclass.enum_id = _

    _vartypes._enum = _enum
    _vartypes._enum_count = _

    _default_platform_vartypes[module.triple] = _vartypes

    return _vartypes

VarTypes = generate_vartypes()

DEFAULT_TYPE = VarTypes._DEFAULT_TYPE
DEFAULT_RETURN_VALUE = VarTypes.DEFAULT_RETURN_VALUE