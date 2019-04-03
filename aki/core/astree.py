from core.error import AkiSyntaxErr


class ASTNode:
    """
    Base type for all AST nodes, with helper functions.
    """

    def __init__(self, p):
        self.p = p
        self.child = None

        self.lineno = p.lineno
        self.index = p.index

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
    pass


class VarType(Expression):
    """
    Variable type, stored as a string.
    """

    def __init__(self, p, vartype: VarTypeNode):
        super().__init__(p)
        # Originally vartype was a string,
        # but it's now its own little AST tree.
        assert isinstance(vartype, VarTypeNode)
        self.vartype = vartype
        self.aki_type = None
        self.llvm_type = None

    def flatten(self):
        return [self.__class__.__name__, self.vartype.flatten()]

    def __eq__(self, other):
        return self.vartype == other.vartype


class VarTypeName(VarTypeNode):
    def __init__(self, p, name: str):
        super().__init__(p)
        self.name = name

    def __eq__(self, other):
        return self.name == other.name

    def flatten(self):
        return [self.__class__.__name__, self.name]


# to come: VarTypePointer, VarTypeCall, etc.


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
            self.vartype.flatten(),
            self.default_value.flatten() if self.default_value else None,
        ]


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
        return [self.__class__.__name__, self.val, self.vartype.flatten()]


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
        raise NotImplementedError

    def flatten(self):
        return [
            self.__class__.__name__,
            self.if_expr.flatten(),
            self.then_expr.flatten(),
            self.else_expr.flatten() if self.else_expr else None,
        ]


class WhenExpr(IfExpr):
    pass


class Prototype(ASTNode):
    """
    Function prototype.
    """

    def __init__(self, p, name: str, arguments, return_type, is_declaration=False):
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

    def flatten(self):
        return [
            self.__class__.__name__,
            self.prototype.flatten(),
            [_.flatten() for _ in self.body.body],
        ]


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

    def flatten(self):
        return [self.__class__.__name__, [_.flatten() for _ in self.body]]


class LLVMOp(Expression):
    """
    Synthetic AST node generated during a binop.
    """

    def __init__(self, node, aki_type, name=None):
        """
        Generates a new synthetic node by using
        an existing AST node (for its position info),
        and an existing Aki type for the type data.
        """

        super().__init__(node.p)
        v_node = VarType(node, Name(node, str(aki_type)[1:]))
        v_node.aki_type = aki_type
        v_node.llvm_type = aki_type.llvm_type
        self.vartype = v_node
        self.name = name


class LLVMInstr(Expression):
    def __init__(self, node, llvm_instr):
        """
        Synthetic AST node that contains a precomputed value, 
        derived from `node`.
        This is used to encapsulate an instruction if we need
        to pass the results of a codegen operation as an argument
        for something that is codegenned.
        """
        super().__init__(node.p)
        self.node = node
        self.llvm_instr = llvm_instr
        self.vartype = llvm_instr.aki.vartype


class LoopExpr(Expression):
    def __init__(self, p, conditions, body):
        super().__init__(p)
        self.conditions = conditions
        self.body = body

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


class WithExpr(Expression):
    def __init__(self, p, varlist: VarList, body: ExpressionBlock):
        super().__init__(p)
        self.varlist = varlist
        self.body = body

    def flatten(self):
        return [
            self.__class__.__name__,
            [_.flatten() for _ in self.varlist.vars],
            self.body.flatten(),
        ]

