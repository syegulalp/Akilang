from llvmlite.ir import types
from llvmlite import ir, binding
import ctypes
from core.astree import BinOpComparison, LLVMInstr, Constant, IfExpr
from typing import Optional


class AkiType:
    """
    Base type for all Aki types.
    """

    llvm_type: ir.Type
    base_type: Optional["AkiType"]
    type_id: Optional[str] = None
    enum_id: Optional[int] = None

    comp_ops = {
        "==": ".eqop",
        "!=": ".neqop",
        "<=": ".leqop",
        ">=": ".geqop",
        "<": ".ltop",
        ">": ".gtop",
    }
    comp_ins: Optional[str] = None

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

    def __str__(self):
        return f":{self.type_id}"

    def __eq__(self, other):
        return self.type_id == other.type_id

    def c(self):
        """
        Return the ctypes representation of this type.
        """
        return self.c_ref[self.signed][self.bits]

    def format_result(self, result):
        """
        Return a __str__-compatible representation for this result,
        as used in the REPL.
        """
        return result


class AkiPointer(AkiType):
    """
    Takes in an Aki type reference,
    and returns a pointer of that type,
    """

    signed = False
    llvm_type: Optional[ir.Type] = None

    def __init__(self, module):
        self.module = module
        self.bits = module.types._pointer_width

    def default(self):
        # Null value for pointer
        return None

    def new(self, base_type: AkiType):
        """
        Create a new pointer type from an existing type.
        """

        new = AkiPointer(self.module)
        new.base_type = base_type
        new.llvm_type = base_type.llvm_type.as_pointer()
        new.type_id = f"ptr {base_type.type_id}"
        return new

    # def format_result(self, result):
    #     return f'<object {hex(result)}>'


class AkiObject(AkiType):
    """
    Type for objects in Aki. This is essentially a header,
    with the actual object referred to by a pointer.
    """

    OBJECT_TYPE = 0
    LENGTH = 1
    OBJECT_POINTER = 2

    def __init__(self, module):
        self.module = module
        self.llvm_type = ir.LiteralStructType(
            (
                # Type of object (enum)
                module.types.u_size.llvm_type,
                # Length of object
                module.types.u_size.llvm_type,
                # Void pointer to object, whatever it may be
                module.types.as_ptr(module.types.u_mem).llvm_type,
            )
        )

    def new(self):
        pass


class AkiFunction(AkiObject):
    """
    Type for function pointers in Aki.
    """

    signed = False

    def __init__(self, arguments, return_type):
        self.arguments = arguments
        # list of decorated AkiType nodes
        self.return_type = return_type
        # single decorated AkiType node

        self.llvm_type = ir.PointerType(
            ir.FunctionType(
                self.return_type.llvm_type, [_.llvm_type for _ in self.arguments]
            )
        )
        self.type_id = f'func({",".join([str(_.aki_type) for _ in self.arguments])}){self.return_type.aki_type}'
        self.name = self.type_id

    def c(self):
        return ctypes.c_void_p

    def default(self):
        return None

    def format_result(self, result):
        if result is None:
            result = 0
        return f'<function "{str(self)}" @ {hex(result)}>'


class AkiIntBoolMathOps:
    """
    Math operations shared between integer and boolean types.
    """

    math_ops = {
        "+": "add",
        "-": "sub",
        "*": "mul",
        "/": "div",
        "&": "bin_and",
        "|": "bin_or",
        "and": "andor",
        "or": "andor",
    }

    def math_op_addop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.add(lhs, rhs, f".{op_name}")

    def math_op_subop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.sub(lhs, rhs, f".{op_name}")

    def math_op_mulop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.mul(lhs, rhs, f".{op_name}")

    def math_op_divop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.sdiv(lhs, rhs, f".{op_name}")

    def math_op_bin_andop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.and_(lhs, rhs, f".{op_name}")

    def math_op_bin_orop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.or_(lhs, rhs, f".{op_name}")

    def math_op_andorop(self, codegen, node, lhs, rhs, op_name):
        # Handles both and and or operations

        if not isinstance(lhs.aki.vartype.aki_type, AkiBool):
            operand = codegen._codegen(
                BinOpComparison(
                    node.lhs,
                    "!=",
                    LLVMInstr(node.lhs, lhs),
                    Constant(
                        node.lhs, lhs.aki.vartype.aki_type.default(), lhs.aki.vartype
                    ),
                )
            )

        else:
            operand = lhs

        if node.op == "and":
            true_op = LLVMInstr(node.rhs, rhs)
            false_op = LLVMInstr(node.lhs, lhs)
        else:
            true_op = LLVMInstr(node.lhs, lhs)
            false_op = LLVMInstr(node.rhs, rhs)
        result_test = codegen._codegen(
            IfExpr(operand.aki, LLVMInstr(operand.aki, operand), true_op, false_op)
        )
        return result_test


class AkiBaseInt(AkiType, AkiIntBoolMathOps):
    """
    Base type for integers.
    """

    def __init__(self, bits, signed):
        self.bits = bits
        self.llvm_type = types.IntType(bits)
        self.signed = signed
        self.type_id = f'{"i" if signed else "u"}{bits}'

    def default(self):
        return 0


class AkiTypeRef(AkiType):
    """
    Type reference type (essentially, an enum).
    """

    comp_ops = {"==": ".eqop", "!=": ".neqop"}
    comp_ins = "icmp_unsigned"

    def __init__(self):
        self.bits = 64
        self.llvm_type = types.IntType(self.bits)
        self.signed = False
        self.type_id = "type"


class AkiBool(AkiType, AkiIntBoolMathOps):
    """
    Aki Boolean type. Bit-compatible, but not type-compatible,
    with an i1.
    """

    comp_ops = {"==": ".eqop", "!=": ".neqop"}
    comp_ins = "icmp_unsigned"

    def __init__(self):
        self.bits = 1
        self.llvm_type = types.IntType(1)
        self.signed = False
        self.type_id = "bool"

    def default(self):
        return False

    def math_op_negop(self, codegen, node, operand):
        lhs = codegen._codegen(Constant(node, 1, operand.aki.vartype))
        return codegen.builder.xor(lhs, operand, "bnegop")

    def format_result(self, result):
        return True if result else False


class AkiInt(AkiBaseInt):
    """
    Signed Aki integer type.
    """

    comp_ins = "icmp_signed"

    def __init__(self, bits):
        super().__init__(bits, True)

    def math_op_negop(self, codegen, node, operand):
        lhs = codegen._codegen(Constant(node, 0, operand.aki.vartype))
        return codegen.builder.sub(lhs, operand, "negop")


class AkiUnsignedInt(AkiBaseInt):
    """
    Unsigned Aki integer type.
    """

    comp_ins = "icmp_unsigned"

    def __init__(self, bits):
        super().__init__(bits, False)


class AkiBaseFloat(AkiType):
    """
    Base type for floating-point Aki types.
    """

    math_ops = {"+": "add", "-": "sub", "*": "mul", "/": "div"}

    def math_op_addop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.fadd(lhs, rhs, f".f{op_name}")

    def math_op_subop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.fsub(lhs, rhs, f".f{op_name}")

    def math_op_mulop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.fmul(lhs, rhs, f".f{op_name}")

    def math_op_divop(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.fdiv(lhs, rhs, f".f{op_name}")

    def math_op_negop(self, codegen, node, operand):
        lhs = codegen._codegen(Constant(node, 0, operand.aki.vartype))
        return codegen.builder.fsub(lhs, operand, "fnegop")

    signed = True
    comp_ins = "fcmp_ordered"

    def default(self):
        return 0.0


class AkiFloat(AkiBaseFloat):
    """
    32-bit floating point Aki type.
    """

    def __init__(self):
        super().__init__()
        self.llvm_type = types.FloatType()
        self.type_id = f"f32"

    def c(self):
        return ctypes.c_float


class AkiDouble(AkiBaseFloat):
    """
    64-bit floating point Aki type.
    """

    def __init__(self):
        super().__init__()
        self.llvm_type = types.DoubleType()
        self.type_id = f"f64"

    def c(self):
        return ctypes.c_double


class AkiArray(AkiType):
    """
    Aki array type.
    """

    def __init__(self, vartype, dimensions):
        super().__init__()
        # With each one we create a nested type structure.
        # Signature: `:array[20,32]:i32`
        # `:array[20]:ptr u64` also OK
        # For a dimensionless array, as in a function signature:
        # `:array[]:i32` (not permitted in a declaration)
        # Each newly created array type signature must be added to the
        # module's enum list


class AkiString(AkiObject, AkiType):
    """
    Type for Aki string constants.
    """

    signed = False
    type_id = "str"

    def __init__(self, module):
        self.module = module
        self.llvm_type = ir.PointerType(module.types.obj.llvm_type)

    def c(self):
        return ctypes.c_void_p

    def default(self):
        return None

    def format_result(self, result):
        if result is None:
            return '""'

        char_p = ctypes.POINTER(ctypes.c_char_p)
        result = ctypes.cast(
            result
            + (self.module.types.obj.OBJECT_POINTER * self.module.types.byte.bits),
            char_p,
        )
        result = ctypes.cast(result.contents, char_p)
        result = f'"{str(ctypes.string_at(result),"utf8")}"'
        return result

    def data(self, text):
        text = text + "\x00"
        data = bytearray(text.encode("utf8"))
        data_array = ir.ArrayType(self.module.types.byte.llvm_type, len(data))
        return data, data_array


class _AkiTypes:
    """
    Holds all Aki type definitions for a given module.
    """

    # These types are universal and so do not need to be instantiated
    # with the module.

    type = AkiTypeRef()
    bool = AkiBool()
    i1 = AkiInt(1)
    i8 = AkiInt(8)
    i16 = AkiInt(16)
    i32 = AkiInt(32)
    int = AkiInt(32)
    i64 = AkiInt(64)
    u8 = AkiUnsignedInt(8)
    u16 = AkiUnsignedInt(16)
    u32 = AkiUnsignedInt(32)
    uint = AkiUnsignedInt(32)
    u64 = AkiUnsignedInt(64)
    f32 = AkiFloat()
    f64 = AkiDouble()

    def __init__(self, module: Optional[ir.Module] = None, bytesize=8):

        if module is None:
            module = ir.Module()

        # Set internal module reference so types can access each other
        module.types = self

        # Obtain pointer size from LLVM target
        target_data = binding.create_target_data(module.data_layout)
        self._byte_width = ir.PointerType(ir.IntType(bytesize)).get_abi_size(
            target_data
        )
        self._pointer_width = self._byte_width * bytesize

        # Set byte and pointer sizes
        self.byte = AkiUnsignedInt(self._byte_width)
        self.u_mem = self.byte
        self.u_size = AkiUnsignedInt(self._pointer_width)

        # Set types that depend on pointer sizes
        self._ptr = AkiPointer(module)
        self.obj = AkiObject(module)
        self.str = AkiString(module)

        # Default type is a 32-bit signed integer
        self._default = self.i32

        # Create type enums
        index = 0
        self.enum_ids: dict = {}
        for _ in (self.__class__.__dict__.items(), self.__dict__.items()):
            for k, v in _:
                if isinstance(v, AkiType):
                    self.enum_ids[index] = v
                    v.enum_id = index
                    index += 1

    def as_ptr(self, other):
        return self._ptr.new(other)

