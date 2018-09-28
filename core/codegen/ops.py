import llvmlite.ir as ir
from core.errors import CodegenError
from core.operators import BUILTIN_UNARY_OP
from core.ast_module import Binary, Number, If
from core.mangling import mangle_args
from core.vartypes import VarTypes, Str

# pylint: disable=E1101

class Ops():

    def _codegen_Unary(self, node):
        operand = self._codegen(node.rhs)
        # TODO: no overflow checking yet!
        if node.op in BUILTIN_UNARY_OP:
            if node.op == 'not':
                if isinstance(operand.type, (ir.IntType, ir.DoubleType)):
                    cond_expr = Binary(node.position, '==', node.rhs,
                                       Number(node.position, 0, operand.type))
                    return self._codegen_If(
                        If(
                            node.position,
                            cond_expr,
                            Number(node.position, 1, operand.type),
                            Number(node.position, 0, operand.type), ))
            elif node.op == '-':
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

        if node.op == '=':
            return self._codegen_Assignment(node.lhs, node.rhs)

        lhs = self._codegen(node.lhs)
        rhs = self._codegen(node.rhs)

        if lhs.type != rhs.type:
            raise CodegenError(
                f'"{lhs.type.describe()}" ({node.lhs.name}) and "{rhs.type.describe()}" ({node.rhs.name}) are incompatible types for operation',
                node.position)
        else:
            vartype = lhs.type
            v_type = getattr(lhs.type, 'v_type', None)

        try:
            # For non-primitive types we need to look up the property

            if v_type is not None:
                if v_type == Str:
                    raise NotImplementedError

            # TODO: no overflow checking!
            # we have to add that when we have exceptions, etc.
            # with fcmp_ordered this is assuming we are strictly comparing
            # float to float in all cases.

            # Integer operations

            if isinstance(vartype, ir.IntType):

                if lhs.type.signed:
                    signed_op = self.builder.icmp_signed
                else:
                    signed_op = self.builder.icmp_unsigned

                if node.op == '+':
                    return self.builder.add(lhs, rhs, 'addop')
                elif node.op == '+=':                   
                    operand = self._get_var(node, lhs)
                    value = self.builder.add(lhs, rhs, 'addop')
                    self.builder.store(value, operand)
                    return value
                elif node.op == '-=':
                    operand = self._get_var(node, lhs)
                    value = self.builder.sub(lhs, rhs, 'addop')
                    self.builder.store(value, operand)
                    return value
                elif node.op == '-':
                    return self.builder.sub(lhs, rhs, 'subop')
                elif node.op == '*':
                    return self.builder.mul(lhs, rhs, 'multop')
                elif node.op == '<':
                    x = signed_op('<', lhs, rhs, 'ltop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '>':
                    x = signed_op('>', lhs, rhs, 'gtop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '>=':
                    x = signed_op('>=', lhs, rhs, 'gteqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '<=':
                    x = signed_op('<=', lhs, rhs, 'lteqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '==':
                    x = signed_op('==', lhs, rhs, 'eqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '!=':
                    x = signed_op('!=', lhs, rhs, 'neqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '/':
                    if int(getattr(rhs, 'constant', 1)) == 0:
                        raise CodegenError('Integer division by zero', node.rhs.position)
                    return self.builder.sdiv(lhs, rhs, 'divop')
                elif node.op == 'and':
                    x = self.builder.and_(lhs, rhs, 'andop') # pylint: disable=E1111
                    x.type = VarTypes.bool
                    return x
                elif node.op == 'or':
                    x = self.builder.or_(lhs, rhs, 'orop') # pylint: disable=E1111
                    x.type = VarTypes.bool
                    return x
                else:
                    return self._codegen_methodcall(node, lhs, rhs)

            # floating-point operations

            elif isinstance(vartype, (ir.DoubleType, ir.FloatType)):

                if node.op == '+':
                    return self.builder.fadd(lhs, rhs, 'faddop')
                elif node.op == '+=':                   
                    operand = self._get_var(node, lhs)
                    value = self.builder.fadd(lhs, rhs, 'faddop')
                    self.builder.store(value, operand)
                    return value
                elif node.op == '-=':
                    operand = self._get_var(node, lhs)
                    value = self.builder.fsub(lhs, rhs, 'fsubop')
                    self.builder.store(value, operand)
                    return value
                elif node.op == '-':
                    return self.builder.fsub(lhs, rhs, 'fsubop')
                elif node.op == '*':
                    return self.builder.fmul(lhs, rhs, 'fmultop')
                elif node.op == '/':
                    return self.builder.fdiv(lhs, rhs, 'fdivop')
                elif node.op == '<':
                    cmp = self.builder.fcmp_ordered('<', lhs, rhs, 'fltop')
                    return self.builder.uitofp(cmp, vartype, 'fltoptodouble')
                elif node.op == '>':
                    cmp = self.builder.fcmp_ordered('>', lhs, rhs, 'fgtop')
                    return self.builder.uitofp(cmp, vartype, 'flgoptodouble')
                elif node.op == '>=':
                    cmp = self.builder.fcmp_ordered('>=', lhs, rhs, 'fgeqop')
                    return self.builder.uitofp(cmp, vartype, 'fgeqopdouble')
                elif node.op == '<=':
                    cmp = self.builder.fcmp_ordered('<=', lhs, rhs, 'fleqop')
                    return self.builder.uitofp(cmp, vartype, 'fleqopdouble')
                elif node.op == '==':
                    x = self.builder.fcmp_ordered('==', lhs, rhs, 'feqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op == '!=':
                    x = self.builder.fcmp_ordered('!=', lhs, rhs, 'fneqop')
                    x.type = VarTypes.bool
                    return x
                elif node.op in ('and', 'or'):
                    raise CodegenError(
                        'Operator not supported for "float" or "double" types',
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
                    if node.op == '==':
                        x = signed_op('==', lhs, rhs, 'eqptrop')
                        x.type = VarTypes.bool
                        return x

            else:
                return self._codegen_methodcall(node, lhs, rhs)

        except NotImplementedError:
            raise CodegenError(
                f'Unknown binary operator {node.op} for {vartype}',
                node.position)            