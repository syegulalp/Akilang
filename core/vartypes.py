from core.llvmlite_custom import Map, _PointerType, MyType
from core.tokens import Dunders

import llvmlite.ir as ir
import ctypes
from llvmlite import binding

from enum import Enum

# Singleton types (these do not require an invocation, they're only created once)


def make_type_as_ptr(my_type):
    def type_as_ptr(addrspace=0):
        t = _PointerType(my_type, addrspace, v_id=my_type.v_id)
        return t

    return type_as_ptr


class Bool(ir.IntType):
    p_fmt = '%i'

    def __new__(cls):
        return super().__new__(cls, 1, False, True)


class SignedInt(ir.IntType):
    p_fmt = '%i'

    def __new__(cls, bits, force=True):
        return super().__new__(cls, bits, force, True)


class UnsignedInt(ir.IntType):
    p_fmt = '%u'

    def __new__(cls, bits, force=True):
        return super().__new__(cls, bits, force, False)


class Float32(ir.FloatType):
    def __new__(cls):
        t = super().__new__(cls)
        t.signed = True
        t.v_id = 'f32'
        t.width = 32
        t.is_obj = False
        t.p_fmt = '%f'
        return t


class Float64(ir.DoubleType):
    def __new__(cls):
        t = super().__new__(cls)
        t.signed = True
        t.v_id = 'f64'
        t.width = 64
        t.is_obj = False
        t.p_fmt = '%f'
        return t


ir.IntType.is_obj = False


class Array(ir.ArrayType):
    is_obj = False

    def __init__(self, my_type, my_len):
        super().__init__(my_type, my_len)
        self.v_id = 'array_' + my_type.v_id
        self.signed = my_type.signed
        self.as_pointer = make_type_as_ptr(self)


class CustomType():
    def __new__(cls, name, types, v_types):
        new_class = ir.global_context.get_identified_type('.class.' + name)
        new_class.elements = types
        new_class.v_types = v_types
        new_class.v_id = name
        new_class.signed = False
        new_class.is_obj = True
        new_class.as_pointer = make_type_as_ptr(new_class)
        return new_class


class ArrayClass(ir.types.LiteralStructType):
    '''
    Type for arrays whose dimensions are defined at compile time.
    '''
    is_obj = True
    enum_id = 0

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

_default_platform_module = ir.Module()
_default_platform_vartypes = {_default_platform_module.triple: None}

# TODO: convert this all into a class, probably for the best

def generate_vartypes(module=None, bytesize=8):

    # if no module, assume current platform
    # cache a copy of the default platform module
    # for the lifetime of the app

    if module is None:
        module = _default_platform_module

    if _default_platform_vartypes.get(module.triple, None) is not None:
        return _default_platform_vartypes[module.triple]

    # Initialize target data for the module.
    target_data = binding.create_target_data(module.data_layout)

    # Set up pointer size and u_size vartype for current hardware.
    _byte_width = (
        ir.PointerType(ir.IntType(bytesize)).get_abi_size(target_data)
    )

    _pointer_width = _byte_width * bytesize

    U_MEM = UnsignedInt(_byte_width)
    U_SIZE = UnsignedInt(_pointer_width)

    # create universal object header
    # the first element in this structure:

    # [[1,2,3,4,5][6]]
    # 1: length of data element
    # 2: pointer to data (if stored externally)
    # 3: refcount (not used yet)
    # 4: is item pointed to by element 1 malloc'?
    # 5: is this object itself malloc'd?
    # 6: actual object data (if any)

    Header = ir.global_context.get_identified_type('.object_header.')
    Header.elements = (
        # total length of data element in bytes as u64
        U_SIZE,

        # pointer to object data
        U_MEM.as_pointer(),  # generic ptr void

        # object descriptor
        U_SIZE,

        # flag for whether or not pointed-to obj (by way of element 1) is dynamically allocated (bool)
        # default is 0
        ir.IntType(1),

        # flag for whether or not this obj is dynam. alloc.
        # default is also 0
        ir.IntType(1),

    )

    Header.packed = True

    # for arrays at compile time, we can encode the dimensions at compile time
    # and any calls will be optimized out to constants anyway
    # need to see if the .initializer property works for runtime

    # Object

    Obj = ir.global_context.get_identified_type('.obj.')
    Obj.elements = (Header,
        ir.IntType(_byte_width)
    )
    Obj.v_id = 'obj'
    Obj.is_obj = True
    Obj.signed = False
    Obj.p_fmt = None
    Obj.as_pointer = make_type_as_ptr(Obj)

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

    Result = ir.global_context.get_identified_type('.result.')
    Result.elements = (Header,
        # OK or err? default is OK
        ir.IntType(1),
        # if false
        ir.IntType(_byte_width).as_pointer(),
        # if true
        ir.IntType(_byte_width).as_pointer(),
    )
    Result.v_id='result'
    Result.is_obj = True
    Result.signed = False

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
    Str.elements = (Header,)
    Str.v_id = 'str'
    Str.is_obj = True
    Str.signed = False
    Str.ext_ptr = UnsignedInt(8, True).as_pointer()
    Str.p_fmt = '%s'
    Str.as_pointer = make_type_as_ptr(Str)

    Err = ir.global_context.get_identified_type('.err.')
    Err.elements = (Header,
        Str
    )
    Err.is_obj = True
    Err.signed = False

    _vartypes = Map({

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

        # non-singleton
        'carray': Array,
        'array': ArrayClass,
        'func': ir.FunctionType,

        # object types
        'str': Str,
        'obj': Obj,

    })

    # add these types in manually, since they just shadow existing ones
    _vartypes['bool'] = _vartypes.u1
    _vartypes['byte'] = _vartypes.u8

    _vartypes._header = Header

    # set platform-dependent sizes
    _vartypes._byte_width = _byte_width
    _vartypes._pointer_width = _pointer_width

    _vartypes._arrayclass = ArrayClass
    _vartypes._carray = Array

    _vartypes._str = type(Str)

    # TODO: this should be moved back into the underlying types?
    _vartypes.f32.c_type = ctypes.c_double
    _vartypes.f64.c_type = ctypes.c_longdouble

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
            _enum[_]=_vartypes[n]
            _vartypes[n].enum_id = _

    _+=1
    _vartypes._arrayclass.enum_id = _
    
    _vartypes._enum = _enum
    _vartypes._enum_count = _
    
    _default_platform_vartypes[module.triple] = _vartypes

    return _vartypes


VarTypes = generate_vartypes()

DEFAULT_TYPE = VarTypes._DEFAULT_TYPE
DEFAULT_RETURN_VALUE = VarTypes.DEFAULT_RETURN_VALUE

dunder_methods = set([f'__{n}__' for n in Dunders])

Str = VarTypes.str
