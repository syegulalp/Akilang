import llvmlite.ir as ir
from core.errors import CodegenError, BlockExit
from core.operators import BUILTIN_UNARY_OP
from core.ast_module import Binary, Number, If
from core.mangling import mangle_args
from core.vartypes import VarTypes, Str
from core.tokens import Ops as Op

# pylint: disable=E1101


class Ops():

    def _codegen_Unary(self, node):
        operand = self._codegen(node.rhs)
        # TODO: no overflow checking yet!
        if node.op in BUILTIN_UNARY_OP:
            if node.op == Op.NOT:
                if isinstance(operand.type, (ir.IntType, ir.DoubleType)):
                    cond_expr = Binary(node.position, Op.EQ, node.rhs,
                                       Number(node.position, 0, operand.type))
                    return self._codegen_If(
                        If(
                            node.position,
                            cond_expr,
                            Number(node.position, 1, operand.type),
                            Number(node.position, 0, operand.type), ))
            elif node.op == Op.NEG:
                lhs = ir.Constant(operand.type, 0)
                if isinstance(operand.type, ir.IntType):
                    return self.builder.sub(lhs, operand, 'negop')
                elif isinstance(operand.type, ir.DoubleType):
                    return self.builder.fsub(lhs, operand, 'fnegop')
        else:
            func = self.module.globals.get(
                f'unary.{node.op}{mangle_args((operand.type,))}')
            if not func:
                raise CodegenError(
                    f'Undefined unary operator "{node.op}" for "{operand.type.describe()}"',
                    node.position)
            return self.builder.call(func, [operand], 'unop')

    def _codegen_Binary(self, node):
        # Assignment is handled specially because it doesn't follow the general
        # recipe of binary ops.

        if node.op == Op.ASSIGN:
            return self._codegen_Assignment(node.lhs, node.rhs)

        lhs = self._codegen(node.lhs)
        rhs = self._codegen(node.rhs)

        # Autopromotion of integer constants
        # must both be positive integers

        try:
            if not (isinstance(lhs, ir.Constant) and isinstance(rhs, ir.Constant)):
                raise BlockExit

            if not (isinstance(lhs.type, ir.IntType) and isinstance(rhs.type, ir.IntType)):
                raise BlockExit

            # future note: unsigned-to-signed is OK as long as the
            # unsigned quantity is half or less the bitwidth of signed
            # eg. u8 to i16 is OK, u8 to i32 is OK
            # but u8 to i8 is not

            # and signed-to-unsigned, the target bitwidth must be double
            # i8 to u16 OK, i8 to u32 OK
            # but i8 to u8, not OK

            # be sure to use sext and zext correctly in the above

            if lhs.type.signed != rhs.type.signed:
                raise BlockExit

            # eventually replace this with tests of the size of the
            # constant vs. the target bitwidth

            if not (int(lhs.constant) > 0 and int(rhs.constant) > 0):
                raise BlockExit

            if lhs.type.width > rhs.type.width:
                rhs = self.builder.zext(rhs, lhs.type)
                rhs.type = lhs.type
            else:
                lhs = self.builder.zext(lhs, rhs.type)
                lhs.type = rhs.type

        except BlockExit:
            pass

        # the above should be made into a function
        # so it can be used in, for instance, call sites

        # next will be autopromotion of variables
        # same signing, one has a lesser bitwidth than the other

        # for issues where one is signed and the other is unsigned,
        # we would need to ensure the signed value is greater than zero
        # I'm not sure we can enforce that for vars at compile time

        # release mode, or some other "strict" compiler directive,
        # should disable these behaviors unless they are specifically
        # re-enabled

        if lhs.type != rhs.type:
            raise CodegenError(
                f'"{lhs.type.describe()}" ({node.lhs.name}) and "{rhs.type.describe()}" ({node.rhs.name}) are incompatible types for operation',
                node.position)
        else:
            vartype = lhs.type

        try:
            if vartype.is_obj_ptr():
                return self._codegen_methodcall(node, lhs, rhs)

            # Integer operations
            # TODO: no overflow checking!

            if isinstance(vartype, ir.IntType):

                if lhs.type.signed:
                    signed_op = self.builder.icmp_signed
                else:
                    signed_op = self.builder.icmp_unsigned

                if node.op == Op.ADD:
                    return self.builder.add(lhs, rhs, 'addop')
                elif node.op == Op.SUBTRACT:
                    return self.builder.sub(lhs, rhs, 'subop')
                elif node.op == Op.MULTIPLY:
                    return self.builder.mul(lhs, rhs, 'multop')
                elif node.op == Op.DIVIDE:
                    if int(getattr(rhs, 'constant', 1)) == 0:
                        raise CodegenError(
                            'Integer division by zero', node.rhs.position)
                    return self.builder.sdiv(lhs, rhs, 'divop')
                elif node.op == Op.LESS_THAN:
                    x = signed_op('<', lhs, rhs, 'ltop')
                    x.type = self.vartypes.bool
                    return x
                elif node.op == Op.GREATER_THAN:
                    x = signed_op('>', lhs, rhs, 'gtop')
                    x.type = self.vartypes.bool
                    return x
                elif node.op == Op.GREATER_THAN_EQ:
                    x = signed_op('>=', lhs, rhs, 'gteqop')
                    x.type = self.vartypes.bool
                    return x
                elif node.op == Op.LESS_THAN_EQ:
                    x = signed_op('<=', lhs, rhs, 'lteqop')
                    x.type = self.vartypes.bool
                    return x
                elif node.op == Op.EQ:
                    x = signed_op('==', lhs, rhs, 'eqop')
                    x.type = self.vartypes.bool
                    return x
                elif node.op == Op.NEQ:
                    x = signed_op('!=', lhs, rhs, 'neqop')
                    x.type = self.vartypes.bool
                    return x

                elif node.op in (Op.AND, Op.B_AND):
                    x = self.builder.and_(
                        lhs, rhs, 'andop')  # pylint: disable=E1111
                    if node.op == Op.AND:
                        x = self.builder.trunc(x,
                                               self.vartypes.bool)
                    return x
                elif node.op in(Op.OR, Op.B_OR):
                    x = self.builder.or_(
                        lhs, rhs, 'orop')  # pylint: disable=E1111
                    if node.op == Op.OR:
                        x = self.builder.trunc(x,
                                               self.vartypes.bool)
                    return x

                else:
                    return self._codegen_methodcall(node, lhs, rhs)

            # floating-point operations

            elif isinstance(vartype, (ir.DoubleType, ir.FloatType)):

                if node.op == Op.ADD:
                    return self.builder.fadd(lhs, rhs, 'faddop')
                elif node.op == Op.SUBTRACT:
                    return self.builder.fsub(lhs, rhs, 'fsubop')
                elif node.op == Op.MULTIPLY:
                    return self.builder.fmul(lhs, rhs, 'fmultop')
                elif node.op == Op.DIVIDE:
                    return self.builder.fdiv(lhs, rhs, 'fdivop')
                elif node.op == Op.LESS_THAN:
                    cmp = self.builder.fcmp_ordered('<', lhs, rhs, 'fltop')
                    cmp.type = self.vartypes.bool
                    return cmp
                elif node.op == Op.GREATER_THAN:
                    cmp = self.builder.fcmp_ordered('>', lhs, rhs, 'fgtop')
                    cmp.type = self.vartypes.bool
                    return cmp
                elif node.op == Op.GREATER_THAN_EQ:
                    cmp = self.builder.fcmp_ordered('>=', lhs, rhs, 'fgeqop')
                    cmp.type = self.vartypes.bool
                    return cmp
                elif node.op == Op.LESS_THAN_EQ:
                    cmp = self.builder.fcmp_ordered('<=', lhs, rhs, 'fleqop')
                    cmp.type = self.vartypes.bool
                    return cmp
                elif node.op == Op.EQ:
                    x = self.builder.fcmp_ordered('==', lhs, rhs, 'feqop')
                    x.type = self.vartypes.bool
                    return x
                elif node.op == Op.NEQ:
                    x = self.builder.fcmp_ordered('!=', lhs, rhs, 'fneqop')
                    x.type = self.vartypes.bool
                    return x
                elif node.op in (Op.AND, Op.B_AND, Op.OR, Op.B_OR, Op.XOR):
                    raise CodegenError(
                        f'Operator "{node.op}" not supported for "float" or "double" types',
                        node.lhs.position)
                else:
                    return self._codegen_methodcall(node, lhs, rhs)

            # Pointer equality

            elif isinstance(vartype, ir.PointerType):
                # TODO: use vartype.is_obj_ptr() to determine
                # if this is a complex object that needs to invoke
                # its __eq__ method, but this is fine for now
                signed_op = self.builder.icmp_unsigned
                if isinstance(rhs.type, ir.PointerType):
                    if node.op == Op.EQ:
                        x = signed_op('==', lhs, rhs, 'eqptrop')
                        x.type = self.vartypes.bool
                        return x
                else:
                    raise NotImplementedError

            else:
                return self._codegen_methodcall(node, lhs, rhs)

        except NotImplementedError:
            raise CodegenError(
                f'Unknown binary operator {node.op} for {vartype}',
                node.position)
