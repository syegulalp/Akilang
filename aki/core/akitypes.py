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


class AkiType:
    comp_ops = {
        "==": ".eqop",
        "!=": ".neqop",
        "<=": ".leqop",
        ">=": ".geqop",
        "<": ".ltop",
        ">": ".gtop",
    }
    comp_ins = None

    def __str__(self):
        return f":{self.type_id}"

    def __eq__(self, other):
        return self.type_id == other.type_id

    def c(self):
        return c_ref[self.signed][self.bits]

    def as_pointer(self):
        return AkiPointer(self)


class AkiPointer(AkiType):
    """
    Takes in an Aki type reference,
    and returns a pointer of that type,
    """

    signed = False
    bits = 64

    def __init__(self, base_type):
        self.base_type = base_type
        self.llvm_type = base_type.llvm_type.as_pointer()
        self.type_id = f"ptr {base_type.type_id}"

    def default(self):
        # Null value for pointer
        return None


class AkiObject(AkiType):
    pass


class AkiFunction(AkiObject):
    signed = False

    def __init__(self, arguments, return_type):
        self.arguments = arguments
        # list of decorated AkiType nodes
        self.return_type = return_type 
        # single decorated AkiType node

        self.llvm_type = ir.FunctionType(
            self.return_type.llvm_type,
            [_.llvm_type for _ in self.arguments]
        )
        self.type_id = f'func({",".join([str(_.aki_type) for _ in self.arguments])}){self.return_type.aki_type}'

    def c(self):
        return ctypes.c_void_p
    
    def default(self):
        return None


class AkiBaseInt(AkiType):
    def __init__(self, bits, signed):
        self.bits = bits
        self.llvm_type = types.IntType(bits)
        self.signed = signed
        self.type_id = f'{"i" if signed else "u"}{bits}'

    def default(self):
        return 0


class AkiTypeRef(AkiType):
    comp_ops = {"==": ".eqop", "!=": ".neqop"}
    comp_ins = "icmp_unsigned"

    def __init__(self):
        self.bits = 64
        self.llvm_type = types.IntType(self.bits)
        self.signed = False
        self.type_id = "type"


class AkiBool(AkiType):
    def __init__(self):
        self.bits = 1
        self.llvm_type = types.IntType(1)
        self.signed = False
        self.type_id = "bool"

    def default(self):
        return False


class AkiInt(AkiBaseInt):
    comp_ins = "icmp_signed"

    def __init__(self, bits):
        super().__init__(bits, True)


class AkiUnsignedInt(AkiBaseInt):
    comp_ins = "icmp_unsigned"

    def __init__(self, bits):
        super().__init__(bits, False)


class AkiBaseFloat(AkiType):
    signed = True
    comp_ins = "fcmp_ordered"

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
        "type": AkiTypeRef(),
        "bool": AkiBool(),
        "i1": AkiInt(1),
        "i8": AkiInt(8),
        "i16": AkiInt(16),
        "i32": AkiInt(32),
        "int": AkiInt(32),
        "i64": AkiInt(64),
        "u8": AkiUnsignedInt(8),
        "u16": AkiUnsignedInt(16),
        "u32": AkiUnsignedInt(32),
        "uint": AkiUnsignedInt(32),
        "u64": AkiUnsignedInt(64),
        "f32": AkiFloat(),
        "f64": AkiDouble(),
        # We originally had these here but they break the pattern
        # we'll figure out later how to work stuff like this in
        # "bigint": lambda x: AkiInt(x)
        # (signed)
    }

    @classmethod
    def setup(cls):
        for index, k_v in enumerate(AkiTypes.base_types.items()):
            k, v = k_v
            setattr(AkiTypes, k, v)
            setattr(getattr(AkiTypes, k), "enum_id", index)


AkiTypes.setup()
DefaultType = AkiTypes.i32
