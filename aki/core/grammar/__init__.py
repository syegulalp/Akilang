from lark import Lark, Transformer, Tree, exceptions
from core import error

from core.astree import (
    Constant,
    VarTypeName,
    ExpressionBlock,
    Name,
    VarList,
    Assignment,
    ObjectRef,
    Argument,
    StarArgument,
    Prototype,
    Function,
    Call,
    BinOp,
    WithExpr,
    BinOpComparison,
    LoopExpr,
    WhileExpr,
    IfExpr,
    Break,
    WhenExpr,
    String,
    SelectExpr,
    CaseExpr,
    DefaultExpr,
    VarTypePtr,
    VarTypeFunc,
    VarTypeAccessor,
    VarTypeNode,
    Accessor,
    UnOp,
    UnsafeBlock,
    Decorator,
    InlineDecorator,
    ConstList,
    External,
    AccessorExpr,
    UniList,
    Return,
)


class AkiTransformer(Transformer):
    def start(self, node):
        """
        Returns a list of AST nodes to evaluate.
        """
        return node

    def toplevel(self, node):
        return node[0]

    def expression(self, node):
        """
        Any single expression.
        """
        return node[0]

    def terminal(self, node):
        """
        A semicolon, which forces an end-of-expression.
        """
        return ExpressionBlock(node[0].pos_in_stream, [])

    def atom(self, node):
        """
        Any *single* reference that returns a value:
        - a constant
        - a variable
        - a function call
        - a slice
        - a parenthetical
        - an expression block
        """
        return node[0]

    def parenthetical(self, node):
        """
        One or more atoms enclosed in a parenthetical.
        """
        return node[1]

    def subexpression(self, node):
        """
        Braces enclosing one or more expressions.
        """
        return ExpressionBlock(node[0].pos_in_stream, node[1:-1])

    def toplevel_decorator(self, node):
        """
        A decorator in a top-level context.
        """
        body = node[1]
        for _ in node[0]:
            pos = _[0]
            name = _[1].value
            args = _[2]
            ret = Decorator(pos.pos_in_stream, name, args, body)
            body = ret
        return ret

    def decorators(self, node):
        """
        One or more decorators.
        """
        return node

    def inline_decorator(self, node):
        raise NotImplementedError

    def decorator(self, node):
        """
        A single decorator.
        """
        return node

    def opt_args(self, node):
        """
        An optional argument list for a decorator.
        """
        return node

    def opt_arglist(self, node):
        """
        The arguments themselves within an optional argument list.
        """
        if not node:
            return node
        return node[0]

    def arglist(self, node):
        """
        An argument list.
        """
        return node

    def argument(self, node):
        """
        Argument for an argument list.
        """
        stararg, name, vartype, default_value = node
        argtype = StarArgument if stararg else Argument
        return argtype(name.pos_in_stream, name.value, vartype, default_value)

    def stararg(self, node):
        """
        A starred argument.
        """
        return node

    def dimensions(self, node):
        """
        Dimensions for an array variable type descriptor.
        """
        return node

    def dimension(self, node):
        """
        Single dimension in a dimension list.
        """
        return node[0]

    def mandatory_vartype(self, node):
        """
        A vartype that is required (with a preceding colon).
        """
        return node[1]

    def arraytypedef(self, node):
        """
        Type definition for an array.
        """
        pos, vartype, pos2, dimensions, _ = node
        return VarTypeAccessor(
            pos.pos_in_stream, vartype, Accessor(pos2.pos_in_stream, dimensions)
        )

    def func_call(self, node):
        """
        Function call.
        """
        return Call(node[0].index, node[0].name, node[2], None)

    def opt_call_args(self, node):
        """
        Optional function call arguments.
        """
        if not node:
            return []
        return node[0]

    def call_arg(self, node):
        """
        Single call argument.
        """
        return node[0]

    def call_args(self, node):
        """
        Set of function call arguments.
        """
        return node

    def function_declaration(self, node):
        """
        Function declaration.
        """
        pos = node[0]
        name = node[1].name
        args = node[3]
        vartype = node[5]
        body = node[6]
        proto = Prototype(pos.pos_in_stream, name, args, vartype)
        func = Function(pos.pos_in_stream, proto, body)
        return func

    def external_declaration(self, node):
        """
        External function declaration.
        """
        pos = node[0]
        name = node[1].name
        args = node[3]
        vartype = node[5]
        proto = Prototype(pos.pos_in_stream, name, args, vartype)
        func = External(pos.pos_in_stream, proto, None)
        return func

    def unsafe_block(self, node):
        """
        Unsafe block declaration.
        """
        return UnsafeBlock(
            node[0].pos_in_stream, ExpressionBlock(node[0].pos_in_stream, [node[1]])
        )

    def opt_varassignments(self, node):
        """
        Optional variable assignments.
        """
        if not node:
            return []
        return node[0]

    def variable_declaration_block(self, node):
        """
        Variable declaration block.
        """
        pos = node[0]
        if isinstance(node[1], Tree):
            vlist = node[2]
        else:
            vlist = node[1]
        return VarList(pos.pos_in_stream, vlist)

    def varassignment(self, node):
        """
        Variable assignment block.
        """
        name = node[0]
        vartype = node[1]
        val = node[2]
        name.vartype = vartype
        name.val = val
        return name

    def varassignments(self, node):
        """
        Variable assignments.
        """
        return node

    def assignments(self, node):
        """
        Assignments list.
        """
        return node

    def opt_assignment(self, node):
        """
        Optional assignment.
        """
        if not node:
            return None
        return node[1]

    def assignment_op(self, node):
        """
        Assignment operation.
        """
        return node[0]

    def single_variable_declaration_block(self, node):
        """
        Block with a single variable declaration, for instance in a loop preamble.
        """
        return VarList(node[0].pos_in_stream, [node[1]])

    def assignment(self, node):
        """
        Variable assignment.
        """
        name = node[0]
        op = node[1]
        if op.type.startswith("SM_"):
            return Assignment(
                op.pos_in_stream,
                "=",
                ObjectRef(op.pos_in_stream, node[0]),
                BinOp(op.pos_in_stream, op.value[0], node[0], node[2]),
            )
        return Assignment(
            op.pos_in_stream, op.value, ObjectRef(name.index, name), node[2]
        )

    def test(self, node):
        """
        Any binop or unop.
        """
        _p("test", node)
        return node

    def or_test(self, node):
        """
        OR test.
        """
        op = node[1]
        return BinOp(op.pos_in_stream, op.value, node[0], node[2])

    def not_test(self, node):
        """
        NOT test.
        """
        x = UnOp(node[0].pos_in_stream, "not", node[1])
        return x

    def fold_binop(self, node):
        """
        Turn multiple binops into a single binop.
        """
        lhs = None
        while len(node) > 0:
            lhs = node.pop(0) if lhs is None else binop
            op = node.pop(0)
            rhs = node.pop(0)
            binop = BinOp(op.pos_in_stream, op.value, lhs, rhs)
        return binop

    and_test = add_ops = mult_ops = fold_binop

    def comparison(self, node):
        lhs = None
        while len(node) > 0:
            lhs = node.pop(0) if lhs is None else binop
            op = node.pop(0)
            rhs = node.pop(0)
            binop = BinOpComparison(op.pos_in_stream, op.value, lhs, rhs)
        return binop

        # TODO: allow multi-way comparison:
        # take the first three elements
        # save the last element (rhs)
        # pack them together into a binop
        # if there are more elements:
        # take the rhs, read the next two, pack those into another binopcomp,
        # pack the two binops as an AND, and preserve that
        # etc.

    def factor_ops(self, node):
        """
        Negation or factoring ops.
        """
        return UnOp(node[0].pos_in_stream, node[0].value, node[1])

    def with_expr(self, node):
        """
        With expression.
        """
        if isinstance(node[1], Tree):
            varlist = node[2]
            body = node[4]
        else:
            varlist = node[1]
            body = node[2]
        return WithExpr(node[0].pos_in_stream, varlist, body)

    def while_expr(self, node):
        """
        While expressiion.
        """
        return WhileExpr(node[0].pos_in_stream, node[1], node[2])

    def if_expr(self, node):
        """
        If expression.
        """
        if node[3] is None:
            return WhenExpr(node[0].pos_in_stream, node[1], node[2], None)
        return IfExpr(node[0].pos_in_stream, node[1], node[2], node[3])

    def return_expr(self, node):
        """
        Return.
        """
        return Return(node[0].pos_in_stream, node[1])

    def when_expr(self, node):
        """
        When expression.
        """
        if len(node) < 4:
            return WhenExpr(node[0].pos_in_stream, node[1], node[2], None)
        return WhenExpr(node[0].pos_in_stream, node[1], node[2], node[3])

    def loop_expr(self, node):
        """
        Loop expression.
        """
        pos = node[0].pos_in_stream
        var = node[2]
        if isinstance(var, Assignment):
            v = var.lhs.expr
        else:
            v = var.vars[0]
        if len(node) > 6:
            return LoopExpr(pos, [node[2], node[3], node[4]], node[6])
        else:
            return LoopExpr(
                pos,
                [node[2], node[3], BinOp(pos, "+", v, Constant(pos, "1", v.vartype))],
                node[5],
            )

    def infinite_loop_expr(self, node):
        """
        Loop with no preamble.
        """
        return LoopExpr(node[0].pos_in_stream, [], node[3])

    def select_expr(self, node):
        """
        Select expression.
        """
        caselist = []
        default_case = None
        for _ in node[3]:
            if isinstance(_, DefaultExpr):
                if default_case is not None:
                    raise error.AkiSyntaxErr(
                        _.index, self.text, "Multiple default cases specified in select"
                    )
                default_case = _
            else:
                caselist.append(_)
        return SelectExpr(node[0].pos_in_stream, node[1], caselist, default_case)

    def cases(self, node):
        """
        Cases for select expression.
        """
        return node

    def case(self, node):
        """
        Case expression.
        """
        if node[0].value == "default":
            return DefaultExpr(node[0].pos_in_stream, None, node[1])
        return CaseExpr(node[0].pos_in_stream, node[1], node[2])

    def optional_else(self, node):
        """
        Optional Else expression.
        """
        if node:
            return node[1]
        return None

    def break_expr(self, node):
        """
        Break expression.
        """
        return Break(node[0].pos_in_stream)

    def array_ref(self, node):
        """
        Array reference.
        """
        pos = node[1]
        accessor = node[2]
        return AccessorExpr(
            pos.pos_in_stream, node[0], Accessor(pos.pos_in_stream, accessor)
        )

    def vartype(self, node):
        """
        Variable type expression.
        """
        name = node[1]
        if isinstance(name, VarTypeNode):
            vt = name
        elif name is None:
            return None
        else:
            vt = VarTypeName(name.index, name.value)
        for _ in node[0]:
            vt = VarTypePtr(name.index, vt)
        return vt

    def opt_vartype(self, node):
        """
        Optional variable type."
        """
        if not node:
            return None
        return node[1]

    def vartypelist(self, node):
        """
        Variable type list.
        """
        if not node:
            return []
        if len(node) == 1 and node[0] is None:
            return []
        return node

    def functypedef(self, node):
        """
        Vartype for function type definition.
        """
        typelist = node[2]
        return_type = node[4]
        return VarTypeFunc(node[0].pos_in_stream, typelist, return_type)

    def ptr_list(self, node):
        """
        Ptr node in var type def.
        """
        return node

    ctrl_chars = {
        # Bell
        "a": "\a",
        # Backspace
        "b": "\b",
        # Form feed
        "f": "\f",
        # Line feed/newline
        "n": "\n",
        # Carriage return
        "r": "\r",
        # Horizontal tab
        "t": "\t",
        # vertical tab
        "v": "\v",
    }

    char_code = {
        # 8-bit ASCII
        "x": 3,
        # 16-bit Unicode
        "u": 5,
        # 32-bit Unicode
        "U": 9,
    }

    def string(self, node):
        """
        String constant.
        """
        node = node[0]
        pos = node.pos_in_stream
        raw_str = node.value[1:-1]
        new_str = []
        subs = raw_str.split("\\")
        # the first one will never be a control sequence
        new_str.append(subs.pop(0))
        _subs = iter(subs)
        strlen = 0
        for n in _subs:
            # a \\ generates an empty sequence
            # so we consume that and generate a single \
            if not n:
                new_str.append("\\")
                n = next(_subs)
                new_str.append(n)
                continue
            s = n[0]
            strlen += len(n)
            if s in self.ctrl_chars:
                new_str.append(self.ctrl_chars[s])
                new_str.append(n[1:])
            elif s in self.char_code:
                r = self.char_code[s]
                hexval = n[1:r]
                try:
                    new_str.append(chr(int(hexval, 16)))
                except ValueError:
                    raise AkiSyntaxErr(
                        Pos(p), self.text, f"Unrecognized hex sequence for character"
                    )
                new_str.append(n[r:])
            elif s in ('"', "'"):
                new_str.append(n[0:])
            else:
                # print(n)
                raise AkiSyntaxErr(
                    Errpos(p, strlen + 2),
                    self.text,
                    f"Unrecognized control sequence in string",
                )

        return String(pos, "".join(new_str), VarTypeName(pos, "str"))

    def const_declaration_block(self, node):
        """
        Constant declaration block.
        """
        return ConstList(node[0].pos_in_stream, node[2])

    def uni_declaration_block(self, node):
        """
        Uni declaration block.
        """
        return UniList(node[0].pos_in_stream, node[2])

    def constant(self, node):
        """
        True/False.
        """
        pos = node[0].pos_in_stream
        return Constant(
            pos, 1 if node[0].value == "True" else 0, VarTypeName(pos, "bool")
        )

    def number(self, node):
        """
        Any number.
        """
        return node[0]

    def name(self, node):
        """
        Name reference.
        """
        return Name(node[0].pos_in_stream, node[0].value)

    def decimal_number(self, node):
        """
        Decimal number.
        """
        number = node[0]
        vartype = node[1]
        if vartype is None:
            vartype = VarTypeName(number.pos_in_stream, "i32")
        return Constant(number.pos_in_stream, int(number.value), vartype)

    def hex_number(self, node):
        """
        Hex number.
        """
        pos = node[0].pos_in_stream
        hex_str = node[0].value
        vartype = node[1]

        if hex_str[1] == "x":
            # 0x00 = unsigned
            sign = "u"
        else:
            # 0h00 = signed
            sign = "i"
        value = int(hex_str[2:], 16)
        if vartype:
            return Constant(pos, value, vartype)
        bytelength = (len(hex_str[2:])) * 4
        if bytelength < 8:
            if value > 1:
                bytelength = 8
                typestr = f"{sign}{bytelength}"
            else:
                typestr = "bool"
        else:
            typestr = f"{sign}{bytelength}"

        return Constant(pos, value, VarTypeName(pos, typestr))

    def float_number(self, node):
        """
        Floating point number.
        """
        number = node[0]
        vartype = node[1]
        if vartype is None:
            vartype = VarTypeName(number.pos_in_stream, "f64")
        return Constant(number.pos_in_stream, float(number.value), vartype)


with open("core/grammar/grammar.lark") as file:
    grammar = file.read()

AkiParser = Lark(
    grammar,
    transformer=AkiTransformer(),
    parser="lalr",
    debug=False,
    ambiguity="explicit",
)


def parse(text, *a, **ka):
    try:
        AkiParser.options.transformer.text = text
        result = AkiParser.parse(text, *a, **ka)
    except exceptions.UnexpectedCharacters as e:
        raise error.AkiSyntaxErr(e.pos_in_stream, text, "Unexpected character")
    except exceptions.UnexpectedToken as e:
        raise error.AkiSyntaxErr(e.pos_in_stream, text, "Unexpected token or keyword")
    return result
