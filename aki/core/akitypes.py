from llvmlite.ir import types
from llvmlite import ir, binding
import ctypes
from core.astree import Constant, IfExpr, BinOp, VarTypeName, LLVMNode
from typing import Optional
from core.error import AkiTypeErr

class AkiType:
    """
    Base type for all Aki types.
    """

    llvm_type: ir.Type
    base_type: Optional["AkiType"]
    type_id: Optional[str] = None
    enum_id: Optional[int] = None

    comp_ins: Optional[str] = None

    comp_ops = {
        "==": ".eqop",
        "!=": ".neqop",
        "<=": ".leqop",
        ">=": ".geqop",
        "<": ".ltop",
        ">": ".gtop",
    }

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


class AkiTypeRef(AkiType):
    """
    Type reference type (essentially, an enum).
    """

    comp_ops = {"==": ".eqop", "!=": ".neqop"}
    comp_ins = "icmp_unsigned"

    def __init__(self, module):
        self.module = module
        self.bits = 64
        self.llvm_type = types.IntType(self.bits)
        self.signed = False
        self.type_id = "type"
        self._default = 0

    def format_result(self, result):
        return f"<type{self.module.typemgr.enum_ids[result]}>"

    def default(self):
        return self._default


class AkiPointer(AkiType):
    """
    Takes in an Aki type reference,
    and returns a pointer of that type,
    """

    signed = False
    llvm_type: Optional[ir.Type] = None

    def __init__(self, module: ir.Module):
        self.module = module
        self.bits = module.typemgr._pointer_width

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

    def __init__(self, module: ir.Module):
        self.module = module
        self.llvm_type = ir.LiteralStructType(
            (
                # Type of object (enum)
                module.types["u_size"].llvm_type,
                # Length of object
                module.types["u_size"].llvm_type,
                # Void pointer to object, whatever it may be
                module.typemgr.as_ptr(module.types["u_mem"]).llvm_type,
            )
        )

    def new(self):
        pass


class AkiFunction(AkiObject):
    """
    Type for function pointers in Aki.
    """

    signed = False

    def __init__(self, arguments: list, return_type: AkiType):
        # list of decorated AkiType nodes
        self.arguments = arguments
        # single decorated AkiType node
        self.return_type = return_type

        self.llvm_type = ir.PointerType(
            ir.FunctionType(
                self.return_type.llvm_type, [_.llvm_type for _ in self.arguments]
            )
        )
        self.type_id = f'func({",".join([str(_.akitype) for _ in self.arguments])}){self.return_type}'
        self.name = self.type_id

    def c(self):
        return ctypes.c_void_p

    def default(self):
        return None

    def format_result(self, result):
        if result is None:
            result = 0
        return f"<function{str(self)} @ {hex(result)}>"


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

        if not isinstance(lhs.akitype, AkiBool):
            lhs_x = codegen._scalar_as_bool(node.lhs, lhs)
        else:
            lhs_x = lhs

        if not isinstance(rhs.akitype, AkiBool):
            rhs_x = codegen._scalar_as_bool(node.rhs, rhs)
        else:
            rhs_x = rhs

        lhs_x = LLVMNode(node.lhs, VarTypeName(node.lhs, lhs.akitype.type_id), lhs_x)
        rhs_x = LLVMNode(node.rhs, VarTypeName(node.rhs, rhs.akitype.type_id), rhs_x)

        if node.op == "and":
            result_test = BinOp(node, "&", lhs_x, rhs_x)
            true_result = LLVMNode(
                node.rhs, VarTypeName(node.rhs, rhs.akitype.type_id), rhs
            )
            false_result = Constant(
                node, rhs.akitype.default(), VarTypeName(node, rhs.akitype.type_id)
            )

            result = IfExpr(node, result_test, true_result, false_result)

        else:

            # first, test if both values are false
            first_result_test = BinOp(node, "|", lhs_x, rhs_x)
            # if so, return 0
            first_false_result = Constant(
                node, lhs.akitype.default(), VarTypeName(node, lhs.akitype.type_id)
            )
            # if not, return the value
            first_true_result = LLVMNode(
                node.lhs, VarTypeName(node.lhs, lhs.akitype.type_id), lhs
            )

            first_result = IfExpr(
                node, first_result_test, first_true_result, first_false_result
            )

            # next, test if the lhs result is nonzero
            second_result_test = BinOp(node, "|", first_result, first_false_result)

            # if so, return that value
            second_true_result = first_true_result

            # if not, return the rhs
            second_false_result = LLVMNode(
                node.rhs, VarTypeName(node.rhs, rhs.akitype.type_id), rhs
            )

            result = IfExpr(
                node, second_result_test, second_true_result, second_false_result
            )

        result = codegen._codegen(result)

        return result


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
        lhs = codegen._codegen(Constant(node, 1, operand.akitype))
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
        lhs = codegen._codegen(Constant(node, 0, operand.akitype))
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
        lhs = codegen._codegen(
            Constant(node, 0.0, VarTypeName(node, operand.akitype.type_id))
        )
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
        self.llvm_type = ir.PointerType(self.module.types["obj"].llvm_type)

    def c(self):
        return ctypes.c_void_p

    def default(self):
        return None

    def format_result(self, result):

        # TODO: eventually we will point to a blank string
        # as the default and not need this

        if result is None:
            return '""'

        # TODO: Let's find a way to automatically GEP this pointer
        # Eventually we'll emit instructions to extract such things
        # e.g., a c_ref attribute for the type that returns an i8*

        char_p = ctypes.POINTER(ctypes.c_char_p)
        result = ctypes.cast(
            result
            + (
                self.module.types["obj"].OBJECT_POINTER * self.module.types["byte"].bits
            ),
            char_p,
        )
        result = ctypes.cast(result.contents, char_p)
        result = f'"{str(ctypes.string_at(result),"utf8")}"'
        return result

    def data(self, text):
        text = text + "\x00"
        data = bytearray(text.encode("utf8"))
        data_array = ir.ArrayType(self.module.types["byte"].llvm_type, len(data))
        return data, data_array


class AkiTypeMgr:

    # These do not rely on any particular architecture,
    # and so are set once and never changed.

    base_types = {
        "bool": AkiBool(),
        "i1": AkiInt(1),
        "i8": AkiInt(8),
        "i16": AkiInt(16),
        "i32": AkiInt(32),
        "i64": AkiInt(64),
        "int": AkiInt(32),
        "u8": AkiUnsignedInt(8),
        "u16": AkiUnsignedInt(16),
        "u32": AkiUnsignedInt(32),
        "u64": AkiUnsignedInt(64),
        "uint": AkiUnsignedInt(32),
        "f32": AkiFloat(),
        "f64": AkiDouble(),
        "float": AkiDouble(),
        "func": AkiFunction,
    }

    def __init__(self, module: Optional[ir.Module] = None, bytesize=8):
        if module is None:
            module = ir.Module()

        # Set internal module reference so types can access each other

        # we might want to set these in the module,
        # back-decorating is an antipattern

        module.typemgr = self

        self.module = module

        # Obtain pointer size from LLVM target
        target_data = binding.create_target_data(module.data_layout)
        self._byte_width = ir.PointerType(ir.IntType(bytesize)).get_abi_size(
            target_data
        )
        self._pointer_width = self._byte_width * bytesize

        self.reset()

    def reset(self):
        # Initialize the type map from the base type list,
        # which never changes

        self.types = dict(self.base_types)
        self.module.types = self.types

        # Set byte and pointer sizes
        self.types["byte"] = AkiUnsignedInt(self._byte_width)
        self.types["u_mem"] = self.types["byte"]
        self.types["u_size"] = AkiUnsignedInt(self._pointer_width)

        # Set types that depend on pointer sizes
        self._ptr = AkiPointer(self.module)
        self.types["obj"] = AkiObject(self.module)
        self.types["str"] = AkiString(self.module)
        self.types["type"] = AkiTypeRef(self.module)

        # Default type is a 32-bit signed integer
        self._default = self.types["i32"]

        self.enum_id_ctr = 0
        self.enum_ids = {}

        for _ in self.types.values():
            setattr(_, "enum_id", self.enum_id_ctr)
            self.enum_ids[self.enum_id_ctr] = _
            self.enum_id_ctr += 1

        self.custom_types = {}

    def as_ptr(self, other):
        return self._ptr.new(other)

    def add_type(self, type_name: str, type_ref: AkiType, module_ref):
        if module_ref.name not in self.custom_types:
            self.custom_types[module_ref.name] = {}
        self.custom_types[module_ref.name][type_name] = type_ref
        setattr(type_ref, "enum_id", self.enum_id_ctr)
        self.enum_ids[self.enum_id_ctr] = type_ref
        self.enum_id_ctr += 1
        return type_ref
