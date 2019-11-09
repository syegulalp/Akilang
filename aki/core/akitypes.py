from llvmlite.ir import types
from llvmlite import ir, binding
import ctypes
from core.astree import Constant, IfExpr, BinOp, VarTypeName, LLVMNode, String, Name
from typing import Optional
from core.error import AkiTypeErr, AkiSyntaxErr


def _int(value: int):
    return ir.Constant(ir.IntType(32), value)


class AkiType:
    """
    Base type for all Aki types.
    """

    llvm_type: ir.Type
    base_type: Optional["AkiType"]
    type_id: Optional[str] = None
    enum_id: Optional[int] = None
    comp_ins: Optional[str] = None
    original_function: Optional[ir.Function] = None
    literal_ptr: bool = False
    bits: int = 0

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

    def c_data(self, codegen, node):
        return node

    def c_size(self, codegen, node, llvm_obj):
        size = llvm_obj.type.get_abi_size(codegen.typemgr.target_data())
        return codegen._codegen(Constant(node, size, codegen.types["u_size"]))


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

    def default(self, codegen, node):
        return self._default


class AkiPointer(AkiType):
    """
    Takes in an Aki type reference,
    and returns a pointer of that type,
    """

    signed = False
    llvm_type: Optional[ir.Type] = None

    comp_ops = {"==": ".eqop", "!=": ".neqop"}
    comp_ins = "icmp_unsigned"

    def __init__(self, module: ir.Module):
        self.module = module
        self.bits = module.typemgr._pointer_width

    def default(self, codegen, node):
        # Null value for pointer
        return None

    def new(self, base_type: AkiType, literal_ptr=False):
        """
        Create a new pointer type from an existing type.
        """

        new = AkiPointer(self.module)
        new.base_type = base_type
        new.llvm_type = base_type.llvm_type.as_pointer()
        new.type_id = f"ptr {base_type.type_id}"
        new.literal_ptr = literal_ptr
        return new

    def format_result(self, result):
        return f"<{self.type_id} @ {hex(result)}>"


class AkiObject(AkiType):
    """
    Type for objects in Aki. This is essentially a header,
    with the actual object in the following structure:
    [
        [header],
        [rest of object]
    ]

    """

    OBJECT_TYPE = 0
    LENGTH = 1
    IS_ALLOCATED = 2
    REFCOUNT = 3

    def __init__(self, module: ir.Module):
        self.module = module
        self.llvm_type = module.context.get_identified_type(".object")
        self.llvm_type.elements = [
            # Type of object (enum)
            module.types["u_size"].llvm_type,
            # Length of object data, minus header
            module.types["u_size"].llvm_type,
            # Was this object allocated from the heap?
            module.types["bool"].llvm_type,
            # refcount for object, not used yet
            module.types["u_size"].llvm_type,
        ]
        # TODO: Have a dummy pointer at end that we use to calculate total size?

        # self.llvm_type.packed=True

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
        self.type_id = f'func({",".join([str(_.akitype)[1:] for _ in self.arguments])}){self.return_type}'
        self.name = self.type_id

    def c(self):
        return ctypes.c_void_p

    def default(self, codegen, node):
        return None

    def format_result(self, result):
        if result is None:
            result = 0
        return f"<function{str(self)} @ {hex(result)}>"


class AkiIntBoolMathOps:
    """
    Math operations shared between integer and boolean types.
    """

    bin_ops = {
        "+": "add",
        "-": "sub",
        "*": "mul",
        "/": "div",
        "&": "bin_and",
        "|": "bin_or",
        "and": "andor",
        "or": "andor",
        "%": "mod",
    }

    def binop_mod(self, codegen, node, lhs, rhs, op_name):
        f1 = codegen.builder.sdiv(lhs, rhs, f".{op_name}1")
        f2 = codegen.builder.mul(f1, rhs, f".{op_name}2")
        return codegen.builder.sub(lhs, f2, f".{op_name}3")

    def binop_add(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.add(lhs, rhs, f".{op_name}")

    def binop_sub(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.sub(lhs, rhs, f".{op_name}")

    def binop_mul(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.mul(lhs, rhs, f".{op_name}")

    def binop_div(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.sdiv(lhs, rhs, f".{op_name}")

    def binop_bin_and(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.and_(lhs, rhs, f".{op_name}")

    def binop_bin_or(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.or_(lhs, rhs, f".{op_name}")

    def binop_andor(self, codegen, node, lhs, rhs, op_name):
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
                node,
                rhs.akitype.default(self, node.rhs),
                VarTypeName(node, rhs.akitype.type_id),
            )

            result = IfExpr(node, result_test, true_result, false_result)

        else:

            # first, test if both values are false
            first_result_test = BinOp(node, "|", lhs_x, rhs_x)
            # if so, return 0
            first_false_result = Constant(
                node,
                lhs.akitype.default(self, node.lhs),
                VarTypeName(node, lhs.akitype.type_id),
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

    def default(self, codegen, node):
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

    def default(self, codegen, node):
        return False

    def unop_neg(self, codegen, node, operand):
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

    def unop_neg(self, codegen, node, operand):
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

    bin_ops = {"+": "add", "-": "sub", "*": "mul", "/": "div"}

    def binop_add(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.fadd(lhs, rhs, f".f{op_name}")

    def binop_sub(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.fsub(lhs, rhs, f".f{op_name}")

    def binop_mul(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.fmul(lhs, rhs, f".f{op_name}")

    def binop_div(self, codegen, node, lhs, rhs, op_name):
        return codegen.builder.fdiv(lhs, rhs, f".f{op_name}")

    def unop_neg(self, codegen, node, operand):
        lhs = codegen._codegen(
            Constant(node, 0.0, VarTypeName(node, operand.akitype.type_id))
        )
        return codegen.builder.fsub(lhs, operand, "fnegop")

    signed = True
    comp_ins = "fcmp_ordered"

    def default(self, codegen, node):
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


class AkiArray(AkiObject, AkiType):
    """
    Aki array type.
    This is a raw array, not managed.
    Arrays should not be stack-allocated.
    """

    signed = None
    name = None

    def __init__(self, module):
        self.module = module

    def new(self, codegen, node, base_type: AkiType, accessors: list):
        new = AkiArray(codegen.module)

        array_type = base_type.llvm_type
        array_type.akitype = base_type
        array_type.akinode = node

        array_aki_type = base_type
        subaccessors = []

        for _ in reversed(accessors):
            accessor_dimension = None
            if isinstance(_, Constant):
                accessor_dimension = _.val
            elif isinstance(_, Name):

                # try:
                #     t_val = codegen.eval_to_result(node,[_])
                # except Exception as e:
                #     print("err", e)

                name_val = codegen._name(node, _.name)
                try:
                    accessor_dimension = name_val.initializer.constant
                except Exception:
                    pass

            if not accessor_dimension:
                raise AkiSyntaxErr(
                    _,
                    codegen.text,
                    f"Only constants (not computed values) allowed for array dimensions",
                )

            array_type = ir.ArrayType(array_type, accessor_dimension)
            subaccessors.append(accessor_dimension)

            subakitype = AkiArray(codegen.module)
            subakitype.llvm_type = array_type
            subakitype.type_id = (
                f"array({base_type})[{','.join([str(_) for _ in subaccessors])}]"
            )

            array_type.akitype = subakitype
            array_type.akinode = node

        new.llvm_type = array_type
        new.type_id = f"array({base_type})[{','.join([str(_) for _ in subaccessors])}]"

        codegen.typemgr.add_type(new.type_id, new, codegen.module)
        return new

    def default(self, codegen, node):
        return None

    def op_index(self, codegen, node, expr):
        current = expr
        akitype_loc = current.type.pointee
        indices = [_int(0)]
        for _ in node.accessors.accessors:
            akitype_loc = akitype_loc.element
            akitype = akitype_loc.akitype
            index = codegen._codegen(_)
            indices.append(index)
        result = codegen.builder.gep(current, indices)
        result.akitype = akitype
        result.akinode = node
        return result

    def c_data(self, codegen, node):
        obj_ptr = codegen.builder.bitcast(
            node, codegen.types["u_mem"].llvm_type.as_pointer(0)
        )
        obj_ptr.akitype = codegen.typemgr.as_ptr(codegen.types["u_mem"])
        obj_ptr.akinode = node.akinode
        return obj_ptr


class AkiString(AkiObject, AkiType):
    """
    Type for Aki string constants.
   
    """

    signed = False
    type_id = "str"

    bin_ops = {"+": "add"}

    def __init__(self, module):
        self.module = module
        self.llvm_type_base = module.context.get_identified_type(".str")
        self.llvm_type_base.elements = [
            # Header block
            module.types["obj"].llvm_type,
            # Pointer to data
            module.typemgr.as_ptr(module.types["u_mem"]).llvm_type,
        ]

        # TODO: we may later use a zero length array as the type,
        # so that we can encode the data directly into the block
        # instead of following a pointer

        self.llvm_type = ir.PointerType(self.llvm_type_base)

    def c(self):
        return ctypes.c_void_p

    def default(self, codegen, node):
        null_str = codegen._codegen(String(node, "", None)).get_reference()
        return null_str

    def binop_add(self, codegen, node, lhs, rhs, op_name):
        pass
        # extract lengths of each string
        #   c_size
        # compute new string length
        # (check for overflow?)
        # (later when we have result types)
        # allocate new header
        #   malloc
        # set details
        #
        # allocate new string body
        #   malloc
        # store string data
        #   =

    def format_result(self, result):
        char_p = ctypes.POINTER(ctypes.c_char_p)
        result1 = ctypes.cast(result, char_p)
        result2 = f'"{str(ctypes.string_at(result1),"utf8")}"'
        return result2

    def data(self, text):
        data = bytearray((text + "\x00").encode("utf8"))
        data_array = ir.ArrayType(self.module.types["byte"].llvm_type, len(data))
        return data, data_array

    def c_data(self, codegen, node):
        obj_ptr = codegen.builder.gep(node, [_int(0), _int(1)])
        obj_ptr = codegen.builder.load(obj_ptr)
        obj_ptr.akitype = codegen.typemgr.as_ptr(codegen.types["u_mem"])
        obj_ptr.akinode = node.akinode
        return obj_ptr

    def c_size(self, codegen, node, llvm_obj):
        obj_ptr = codegen.builder.gep(
            llvm_obj, [_int(0), _int(0), _int(AkiObject.LENGTH)]
        )
        obj_ptr = codegen.builder.load(obj_ptr)
        obj_ptr.akitype = codegen.types["u_size"]
        obj_ptr.akinode = llvm_obj.akinode
        return obj_ptr


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
            module.triple = binding.Target.from_default_triple().triple

        # Set internal module reference so types can access each other

        # TODO: we might want to set these in the module,
        # back-decorating is an antipattern

        module.typemgr = self

        self.module = module

        # Obtain pointer size from LLVM target
        self._byte_width = ir.PointerType(ir.IntType(bytesize)).get_abi_size(
            self.target_data()
        )
        self._pointer_width = self._byte_width * bytesize

        self.reset()

        self.const_enum = 0

    # Do not move this, otherwise we can't serialize the type mgr
    def target_data(self):
        return binding.create_target_data(self.module.data_layout)

    def reset(self):
        # Initialize the type map from the base type list,
        # which never changes

        self.custom_types = {}

        self.enum_id_ctr = 0
        self.enum_ids = {}

        self.types = dict(self.base_types)
        self.module.types = self.types

        # Set byte and pointer sizes
        self.types["byte"] = AkiUnsignedInt(self._byte_width)
        self.types["u_mem"] = self.types["byte"]
        self.types["u_size"] = AkiUnsignedInt(self._pointer_width)

        # TODO: u_mem and u_size should be registered types
        # they might not be u8 or u64 on all platforms!

        # Set types that depend on pointer sizes
        self._ptr = AkiPointer(self.module)
        self.types["obj"] = AkiObject(self.module)
        self.types["str"] = AkiString(self.module)
        self.types["type"] = AkiTypeRef(self.module)
        self.types["array"] = AkiArray(self.module)

        # Default type is a 32-bit signed integer
        self._default = self.types["i32"]

        for _ in self.types.values():
            setattr(_, "enum_id", self.enum_id_ctr)
            self.enum_ids[self.enum_id_ctr] = _
            self.enum_id_ctr += 1

    def as_ptr(self, *a, **ka):
        new = self._ptr.new(*a, **ka)
        # TODO: move this into the actual `new` method?
        self.add_type(new.type_id, new, self.module)
        return new

    def add_type(self, type_name: str, type_ref: AkiType, module_ref):
        if type_name in self.custom_types:
            return self.custom_types[type_name]
        self.custom_types[type_name] = type_ref
        setattr(type_ref, "enum_id", self.enum_id_ctr)
        self.enum_ids[self.enum_id_ctr] = type_ref
        self.enum_id_ctr += 1
        return type_ref
