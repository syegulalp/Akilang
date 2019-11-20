from core.error import AkiSyntaxErr
from llvmlite import ir
from typing import Optional


class ASTNode:
    """
    Base type for all AST nodes, with helper functions.
    """

    def __init__(self, index):
        self.child = None
        self.index = index

    def __eq__(self, other):
        raise NotImplementedError

    def flatten(self):
        return [self.__class__.__name__, "flatten unimplemented"]


class Expression(ASTNode):
    """
    Base type for all expressions.
    """

    pass


class Keyword(ASTNode):
    """
    Base type for keywords.
    """

    pass


class TopLevel(ASTNode):
    """
    Mixin type for top-level AST nodes.
    """

    pass


class VarTypeNode(Expression):
    name: Optional[str] = None


class VarTypeName(VarTypeNode):
    def __init__(self, p, name: str):
        super().__init__(p)
        self.name = name

    def __eq__(self, other):
        return self.name == other.name

    def flatten(self):
        return [self.__class__.__name__, self.name]


class VarTypePtr(VarTypeNode):
    def __init__(self, p, pointee: VarTypeNode):
        super().__init__(p)
        self.pointee = pointee
        self.name = f"ptr {pointee.name}"

    def __eq__(self, other):
        return self.pointee == other.pointee

    def flatten(self):
        return [self.__class__.__name__, self.pointee.flatten()]


class VarTypeFunc(VarTypeNode):
    def __init__(self, p, arguments, return_type: VarTypeNode):
        super().__init__(p)
        self.arguments = arguments
        self.return_type = return_type

    def __eq__(self, other):
        return (
            self.arguments == other.arguments and self.return_type == other.return_type
        )

    def flatten(self):
        return [
            self.__class__.__name__,
            self.arguments.flatten() if self.arguments else [],
            self.return_type.flatten() if self.return_type else None,
        ]


class VarTypeAccessor(VarTypeNode):
    def __init__(self, p, vartype: VarTypeNode, accessors: list):
        super().__init__(p)
        self.vartype = vartype
        self.accessors = accessors
        # self.name = f"array({vartype.name})[{','.join([str(_[0]) for _ in accessors.accessors])}]"

    def __eq__(self, other):
        return self.vartype == other.vartype and self.accessors == other.accessors

    def flatten(self):
        return [
            self.__class__.__name__,
            self.vartype.flatten(),
            self.accessors.flatten() if self.accessors else [],
        ]


class Name(Expression):
    """
    Variable reference.
    """

    def __init__(self, p, name, val=None, vartype=None):
        super().__init__(p)
        self.name = name
        self.val = val
        # `val` is only used in variable assignment form
        self.vartype = vartype

    def __eq__(self, other):
        return self.name == other.name

    def flatten(self):
        return [
            self.__class__.__name__,
            self.name,
            self.val.flatten() if self.val else None,
            self.vartype.flatten() if self.vartype else None,
        ]


class VarList(Expression):
    """
    `var` declaration with one or more variables.
    """

    def __init__(self, p, vars):
        super().__init__(p)
        self.vars = vars

    def __eq__(self, other):
        return self.vars == other.vars

    def flatten(self):
        return [
            self.__class__.__name__,
            [_.flatten() for _ in self.vars] if self.vars else [],
        ]


class UniList(TopLevel, VarList):
    pass


class ConstList(TopLevel, VarList):
    pass


class Argument(ASTNode):
    """
    Function argument, with optional type declaration.
    """

    def __init__(self, p, name, vartype=None, default_value=None):
        super().__init__(p)
        self.name = name
        self.vartype = vartype
        self.default_value = default_value

    def __eq__(self, other):
        return self.name == other.name and self.vartype == other.vartype

    def flatten(self):
        return [
            self.__class__.__name__,
            self.name,
            self.vartype.flatten() if self.vartype else None,
            self.default_value.flatten() if self.default_value else None,
        ]


class StarArgument(Argument):
    pass


class Constant(Expression):
    """
    LLVM constant value.
    """

    def __init__(self, p, val, vartype):
        super().__init__(p)
        self.val = val
        self.vartype = vartype

    def __eq__(self, other):
        return self.val == other.val and self.vartype == other.vartype

    def flatten(self):
        return [self.__class__.__name__, self.val, self.vartype.flatten() if self.vartype is not None else None]


class String(Expression):
    """
    String constant.
    """

    def __init__(self, p, val, vartype):
        super().__init__(p)
        self.val = val
        self.vartype = vartype
        self.name = f'"{val}"'

    def __eq__(self, other):
        return self.val == other.val

    def flatten(self):
        return [self.__class__.__name__, self.val]


class UnOp(Expression):
    """
    Unary operator expression.
    """

    def __init__(self, p, op, lhs):
        super().__init__(p)
        self.op = op
        self.lhs = lhs

    def __eq__(self, other):
        return self.op == other.op and self.lhs == other.lhs

    def flatten(self):
        return [self.__class__.__name__, self.op, self.lhs.flatten()]


class RefExpr(Expression):
    """
    Reference expression (obtaining a pointer to an object)
    """

    def __init__(self, p, ref):
        super().__init__(p)
        self.ref = ref

    def __eq__(self, other):
        return self.ref == other.ref

    def flatten(self):
        return [self.__class__.__name__, self.ref.flatten()]


class DerefExpr(RefExpr):
    pass


class BinOp(Expression):
    """
    Binary operator expression.
    """

    def __init__(self, p, op, lhs, rhs):
        super().__init__(p)
        self.op = op
        self.lhs = lhs
        self.rhs = rhs

    def __eq__(self, other):
        return self.op == other.op and self.lhs == other.lhs and self.rhs == other.rhs

    def flatten(self):
        return [
            self.__class__.__name__,
            self.op,
            self.lhs.flatten(),
            self.rhs.flatten(),
        ]


class Assignment(BinOp):
    pass


class BinOpComparison(BinOp):
    pass


class IfExpr(ASTNode):
    def __init__(self, p, if_expr, then_expr, else_expr=None):
        super().__init__(p)
        self.if_expr = if_expr
        self.then_expr = then_expr
        self.else_expr = else_expr

    def __eq__(self, other):
        return (
            self.if_expr == other.if_expr
            and self.then_expr == other.then_expr
            and self.else_expr == other.else_expr
        )

    def flatten(self):
        return [
            self.__class__.__name__,
            self.if_expr.flatten(),
            self.then_expr.flatten(),
            self.else_expr.flatten() if self.else_expr else None,
        ]


class WhenExpr(IfExpr):
    pass

class Return(ASTNode):
    def __init__(self, p, return_val):
        super().__init__(p)
        self.return_val = return_val
    
    def __eq__(self, other):
        return (
            self.return_val == other.return_val
        )
    
    def flatten(self):
        return [
            self.__class__.__name__,
            self.return_val.flatten()
        ]

class Prototype(ASTNode):
    """
    Function prototype.
    """

    def __init__(
        self,
        p,
        name: str,
        arguments: list,
        return_type: VarTypeNode,
        is_declaration=False,
    ):
        super().__init__(p)
        self.name = name
        self.arguments = arguments
        self.return_type = return_type
        self.is_declaration = is_declaration

    def __eq__(self, other):
        return (
            self.arguments == other.arguments and self.return_type == other.return_type
        )

    def flatten(self):
        return [
            self.__class__.__name__,
            self.name,
            [_.flatten() for _ in self.arguments] if self.arguments else [],
            self.return_type.flatten() if self.return_type else None,
        ]


class Function(TopLevel, ASTNode):
    """
    Function body.
    """

    def __init__(self, p, prototype, body):
        super().__init__(p)
        self.prototype = prototype
        self.body = body

    def __eq__(self, other):
        return self.prototype == other.prototype and self.body == other.body

    def flatten(self):
        return [
            self.__class__.__name__,
            self.prototype.flatten(),
            [_.flatten() for _ in self.body],
        ]


class External(Function):
    pass


class Call(Expression, Prototype):
    """
    Function call.
    Re-uses Prototype since it has the same basic structure.
    Arguments contains a list of Expression-class ASTs.
    """

    pass


class ExpressionBlock(Expression):
    """
    {}-delimeted set of expressions, stored as a list in `body`.
    """

    def __init__(self, p, body):
        super().__init__(p)
        self.body = body

    def __eq__(self, other):
        return self.body == other.body

    def flatten(self):
        return [self.__class__.__name__, [_.flatten() for _ in self.body]]


class LLVMNode(Expression):
    """
    Repackages an LLVM op as if it were an unprocessed AST node.
    You should use this if:
    a) you have an op that has been produced by a previous codegen action
    b) you're going to codegen a synthetic AST node using that result as a parameter        
    """

    def __init__(self, node, vartype, llvm_node):
        super().__init__(node.index)

        # Aki node, for position information
        self.node = node

        # Vartype (an AST vartype node provided by the caller)
        # This can also also be an .akitype node
        # so it can just be copied from the last instruction

        self.vartype = vartype

        # LLVM node
        # This MUST have .akitype and .akinode data

        assert isinstance(self.llvm_node, ir.Instruction)

        self.llvm_node = llvm_node
        assert self.llvm_node.akinode
        assert self.llvm_node.akitype

        # Name (optional)
        self.name = None


class LoopExpr(Expression):
    def __init__(self, p, conditions, body):
        super().__init__(p)
        self.conditions = conditions
        self.body = body

    def __eq__(self, other):
        return self.conditions == other.conditions and self.body == other.body

    def flatten(self):
        return [
            self.__class__.__name__,
            [_.flatten() for _ in self.conditions],
            self.body.flatten(),
        ]


class Break(Expression):
    def __init__(self, p):
        super().__init__(p)

    def flatten(self):
        return [self.__class__.__name__]

    def __eq__(self, other):
        return self.__class__ == other.__class__


class WithExpr(Expression):
    def __init__(self, p, varlist: VarList, body: ExpressionBlock):
        super().__init__(p)
        self.varlist = varlist
        self.body = body

    def __eq__(self, other):
        return self.varlist == other.varlist and self.body == other.body

    def flatten(self):
        return [
            self.__class__.__name__,
            [_.flatten() for _ in self.varlist.vars],
            self.body.flatten(),
        ]


class ChainExpr(Expression):
    def __init__(self, p, expr_chain: list):
        super().__init__(p)
        self.expr_chain = expr_chain

    def __eq__(self, other):
        return self.expr_chain == other.expr_chain

    def flatten(self):
        return [self.__class__.__name__, [_.flatten() for _ in self.expr_chain]]


class UnsafeBlock(Expression):
    def __init__(self, p, expr_block):
        super().__init__(p)
        self.expr_block = expr_block

    def __eq__(self, other):
        return self.expr_block == other.expr_block

    def flatten(self):
        return [self.__class__.__name__, [_.flatten() for _ in self.expr_block]]


class Accessor(Expression):
    def __init__(self, p, accessors):
        super().__init__(p)
        self.accessors = accessors

    def __eq__(self, other):
        return self.accessors == other.accessors

    def flatten(self):
        return [self.__class__.__name__, [_.flatten() for _ in self.accessors]]


class AccessorExpr(Expression):
    def __init__(self, p, expr, accessors):
        super().__init__(p)
        self.expr = expr
        self.accessors = accessors

    def __eq__(self, other):
        return self.expr == other.expr and self.accessors == other.accessors

    def flatten(self):
        return [
            self.__class__.__name__,
            self.expr.flatten(),
            [_.flatten() for _ in self.accessors],
        ]


class ObjectRef(Expression):
    """
    Target of an assignment operation.
    The expr in question is a name, etc.
    In every case we want to return a reference to the object,
    not its value.
    """

    def __init__(self, p, expr):
        super().__init__(p)
        self.expr = expr

    def __eq__(self, other):
        return self.expr == other.expr

    def flatten(self):
        return [self.__class__.__name__, self.expr.flatten()]


class ObjectValue(Expression):
    """
    Extracted value.
    """

    def __init__(self, p, expr):
        super().__init__(p)
        self.expr = expr

    def __eq__(self, other):
        return self.expr == other.expr

    def flatten(self):
        return [self.__class__.__name__, self.expr.flatten()]


class SelectExpr(Expression):
    """
    `select` expression.
    """

    def __init__(self, p, select_expr, case_list: list, default_case=None):
        super().__init__(p)
        self.select_expr = select_expr
        self.case_list = case_list
        self.default_case = default_case

    def __eq__(self, other):
        return (
            self.select_expr == other.select_expr
            and self.case_list == other.case_list
            and self.default_case == other.default_case
        )

    def flatten(self):
        return [
            self.__class__.__name__,
            self.select_expr.flatten(),
            [_.flatten() for _ in self.case_list],
        ]


class CaseExpr(Expression):
    """
    `case` expression.
    """

    def __init__(self, p, case_value, case_expr):
        super().__init__(p)
        self.case_value = case_value
        self.case_expr = case_expr

    def __eq__(self, other):
        return self.case_value == other.case_value and self.case_expr == other.case_expr

    def flatten(self):
        return [
            self.__class__.__name__,
            self.case_value.flatten(),
            self.case_expr.flatten(),
        ]

class DefaultExpr(CaseExpr):
    pass


class WhileExpr(Expression):
    """
    `while` expression.
    """

    def __init__(self, p, while_value, while_expr):
        super().__init__(p)
        self.while_value = while_value
        self.while_expr = while_expr

    def __eq__(self, other):
        return (
            self.while_value == other.while_value
            and self.while_expr == other.while_expr
        )

    def flatten(self):
        return [
            self.__class__.__name__,
            self.while_value.flatten(),
            self.while_expr.flatten(),
        ]


class BaseDecorator(Expression):
    def __init__(self, p, name, args, expr_block):
        super().__init__(p)
        self.name = name
        self.args = args
        self.expr_block = expr_block

    def __eq__(self, other):
        return self.name == other.name and self.args == other.args

    def flatten(self):
        return [
            self.__class__.__name__,
            self.name,
            self.args.flatten() if self.args else [],
            self.expr_block.flatten(),
        ]


class Decorator(BaseDecorator, TopLevel):
    pass


class InlineDecorator(Decorator):
    pass
