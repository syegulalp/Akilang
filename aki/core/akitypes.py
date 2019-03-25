from llvmlite.ir import types
from llvmlite import ir
import ctypes

c_ref = {
    True: {
        8: ctypes.c_byte,
        16: ctypes.c_int16,
        32: ctypes.c_int32,
        64: ctypes.c_int64,
    },
    False: {
        1: ctypes.c_bool,
        8: ctypes.c_ubyte,
        16: ctypes.c_uint16,
        32: ctypes.c_uint32,
        64: ctypes.c_uint64,
    },
}


class AkiProperties:
    """
    Used to store a copy of the Aki type and AST objects
    in an LLVM object, so that they can be accessed after
    codegen of that object.

    These objects are attached to an LLVM value such as an Instruction.
    They are NOT attached to the TYPE of that instruction!
    """

    def __init__(self, aki_type=None, name=None, value=None):
        self.vartype = aki_type
        self.name = name
        self.value = value


class AkiType:
    def __str__(self):
        return f":{self.type_id}"

    def __eq__(self, other):
        return self.type_id == other.type_id

    def c(self):
        return c_ref[self.signed][self.bits]

    def as_pointer(self, llvm_var):
        """
        Takes in an LLVM variable reference,
        and returns a pointer of that type,
        decorated with an appropriate .aki subobject.
        """
        pass


class AkiPointer(AkiType):
    pass


class AkiObject(AkiType):
    pass


class AkiFunction(AkiObject):
    signed = False

    def __init__(self, llvm_func):
        self.llvm_type = llvm_func.type
        self.type_id = f"func()"

    def c(self):
        return ctypes.c_void_p


class AkiBaseInt(AkiType):
    def __init__(self, bits, signed):
        self.bits = bits
        self.llvm_type = types.IntType(bits)
        self.signed = signed
        self.type_id = f'{"i" if signed else "u"}{bits}'

    def default(self):
        return 0


class AkiBool(AkiType):
    def __init__(self):
        self.bits = 1
        self.llvm_type = types.IntType(1)
        self.signed = False
        self.type_id = "bool"

    def default(self):
        return False


class AkiInt(AkiBaseInt):
    def __init__(self, bits):
        super().__init__(bits, True)


class AkiUnsignedInt(AkiBaseInt):
    def __init__(self, bits):
        super().__init__(bits, False)


class AkiBaseFloat(AkiType):
    signed = True

    def default(self):
        return 0.0


class AkiFloat(AkiBaseFloat):
    def __init__(self):
        super().__init__()
        self.llvm_type = types.FloatType()
        self.type_id = f"f32"

    def c(self):
        return ctypes.c_float


class AkiDouble(AkiBaseFloat):
    def __init__(self):
        super().__init__()
        self.llvm_type = types.DoubleType()
        self.type_id = f"f64"

    def c(self):
        return ctypes.c_double


class AkiTypes:

    # These are never modified so we can place them in the underlying class

    base_types = {
        "bool": AkiBool(),
        "i1": AkiInt(1),
        "i8": AkiInt(8),
        "i16": AkiInt(16),
        "i32": AkiInt(32),
        "i64": AkiInt(64),
        "u8": AkiUnsignedInt(8),
        "u16": AkiUnsignedInt(16),
        "u32": AkiUnsignedInt(32),
        "u64": AkiUnsignedInt(64),
        "f32": AkiFloat(),
        "f64": AkiDouble(),
        "int": lambda x: AkiInt(x),
        "uint": lambda x: AkiUnsignedInt(x),
    }

    @classmethod
    def setup(cls):
        for k, v in AkiTypes.base_types.items():
            setattr(AkiTypes, k, v)


AkiTypes.setup()
DefaultType = AkiTypes.i32
