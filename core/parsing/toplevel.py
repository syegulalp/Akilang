from core.lexer import TokenKind
from core.ast_module import (
    Array,
    Const,
    Uni,
    String,
    Function,
    Prototype,
    Number,
    Variable,
    DEFAULT_PREC,
    Unary,
    Pragma,
    ItemList,
)
from core.operators import UNASSIGNED, set_binop_info, Associativity
from core.errors import ParseError
from core.tokens import Ops, Puncs

# pylint: disable=E1101


class Toplevel:
    def _parse_pragma_expr(self):
        start = self.cur_tok.position

        # first, consume "pragma"
        self._get_next_token()

        self._match(TokenKind.PUNCTUATOR, Puncs.OPEN_CURLY)

        pragmas = []

        while True:
            if self._cur_tok_is_punctuator(Puncs.CLOSE_CURLY):
                self._get_next_token()
                break
            t = self._parse_expression()
            pragmas.append(t)

        return Pragma(start, pragmas)

    def _parse_var_declaration(self):
        """
        Parse variable declarations in uni/var/const blocks.
        """

        # Not used for variable *references*, which are a little different.
        # Doesn't yet handle initializer assignment because that's handled
        # differently in each case, but maybe later we can unify it

        # first, consume the name of the identifier

        self._compare(TokenKind.IDENTIFIER)
        self._check_builtins()
        name = self.cur_tok.value
        self._get_next_token()

        # check for a vartype

        if self._cur_tok_is_punctuator(Puncs.COLON):
            self._get_next_token()
            vartype = self._parse_vartype_expr()

        else:
            vartype = None

        # check for array declaration

        if self._cur_tok_is_punctuator(Puncs.OPEN_BRACKET):
            arr_start = self.cur_tok.position
            elements = self._parse_array_accessor()

            # I don't think we need to extract a pointer type here.
            # We had this before but I'm leaving it in for reference.
            # oo = getattr(vartype, 'pointee', None)
            # if oo is not None:
            #     print (oo)
            #     vartype = oo

            vartype = Array(arr_start, elements, vartype)
            self._get_next_token()

        return name, vartype

    def _parse_uni_expr(self, const=False):

        self.expr_stack.append(self._parse_uni_expr)

        if const:
            ast_type = Const
        else:
            ast_type = Uni

        self._get_next_token()  # consume the 'uni/const'

        if self._cur_tok_is_punctuator(Puncs.OPEN_CURLY):
            is_bracketed = True
            self._get_next_token()
        else:
            is_bracketed = False

        vars = []

        # TODO: merge this code with parse_var eventually
        # right now we can't do this because of some subtle differences
        # between how const/uni and regular vars are processed

        while True:

            start = self.cur_tok.position

            name, vartype = self._parse_var_declaration()

            # Parse the optional initializer
            if self._cur_tok_is_operator(Ops.ASSIGN):
                self._get_next_token()  # consume the '='
                self.compile_constant = ast_type
                init = self._parse_expression()
                self.compile_constant = None
            else:
                init = None

            if isinstance(init, String):
                init.anonymous = False

            # TODO: use existing eval_and_return for this
            # merge with other functions if possible

            if const and init and not isinstance(init, ItemList):
                if hasattr(init, "val"):
                    self.consts[name] = Number(start, init.val, init.vartype)
                else:

                    # if there's no constant value on the initializer,
                    # it's an expression, and so we need to
                    # JIT-compile the existing constants
                    # to compute the value of that expression

                    # TODO: keep this as a running list whenever
                    # we add consts, so it doesn't have to be reconstructed
                    # from scratch every single time
                    # this could create some really hairy compile times later on
                    # if we don't do that

                    tt = []
                    for k, v in self.consts.items():
                        tt.append(Variable(v.position, k, None, initializer=v))

                    t = ast_type(self.cur_tok.position, tt)

                    # TODO: move the below into evaluator
                    # maybe as `._eval_value`?

                    self.init_evaluator()

                    # Evaluate the temporary AST with the unis/consts
                    # self.evaluator.reset()
                    self.evaluator._eval_ast(t)

                    # Codegen a function that obtains the computed result
                    # for this constant
                    self.evaluator.codegen.generate_code(
                        Function.Anonymous(start, init)
                    )

                    # Extract the variable type of that function
                    r_val = self.evaluator.codegen.module.globals[
                        Prototype.anon_name(Prototype)
                    ].return_value

                    r_type = r_val.type

                    # Run the function with the proper return type
                    e = self.evaluator._eval_ast(
                        Function.Anonymous(start, init, vartype=r_type),
                        return_type=r_type.c_type,
                    )

                    # TODO: use an AST node type that complements the results
                    # this way we can use strings, etc.
                    # need to have a reference in each vartype to
                    # an AST node type

                    # Extract and assign the value
                    init = Number(start, e.value, e.ast.proto.vartype)
                    self.consts[name] = init

            vars.append(Variable(start, name, vartype, initializer=init))

            if is_bracketed:

                if self._cur_tok_is_punctuator(Puncs.COMMA):
                    self._get_next_token()

                if self._cur_tok_is_punctuator(Puncs.CLOSE_CURLY):
                    self._get_next_token()
                    self.expr_stack.pop()
                    return ast_type(self.cur_tok.position, vars)

            else:

                if self._cur_tok_is_punctuator(Puncs.COMMA):
                    self._get_next_token()
                else:
                    self._get_next_token()
                    self.expr_stack.pop()
                    return ast_type(self.cur_tok.position, vars)

            if self.cur_tok.kind in (TokenKind.IDENTIFIER, TokenKind.VARTYPE):
                continue

            raise ParseError(
                f'Expected variable declaration but got "{self.cur_tok.value}" instead',
                self.cur_tok.position,
            )

    def _parse_expression(self):
        self.level += 1
        lhs = self._parse_primary()
        self.level -= 1

        # Start with precedence 0 because we want to bind any operator to the
        # expression at this point.

        return self._parse_binop_rhs(0, lhs)

    def _parse_unaryop_expr(self):
        start = self.cur_tok.position
        op = self.cur_tok.value
        self._get_next_token()
        rhs = self._parse_primary()
        return Unary(start, op, rhs)

    def _parse_prototype(self, extern=False):
        start = self.cur_tok.position
        prec = DEFAULT_PREC
        vartype = None

        if self.cur_tok.kind == TokenKind.STRING:
            name = self.cur_tok.value
            r_name = name
            self._get_next_token()

        elif self.cur_tok.kind == TokenKind.IDENTIFIER:
            self._check_builtins()
            name = self.cur_tok.value
            r_name = name
            self._get_next_token()

        elif self.cur_tok.kind == TokenKind.UNARY:
            self._get_next_token()
            if self.cur_tok.value not in UNASSIGNED:
                raise ParseError(
                    f'Expected unassigned operator after "unary", got {self.cur_tok.value} instead',
                    self.cur_tok.position,
                )
            name = f"unary.{self.cur_tok.value}"
            r_name = self.cur_tok.value
            self._get_next_token()

        elif self.cur_tok.kind == TokenKind.BINARY:
            self._get_next_token()
            if self.cur_tok.kind not in (TokenKind.IDENTIFIER, TokenKind.OPERATOR):
                raise ParseError(
                    f'Expected identifier or unassigned operator after "binary", got {self.cur_tok.value} instead',
                    self.cur_tok.position,
                )
            name = f"binary.{self.cur_tok.value}"
            r_name = self.cur_tok.value
            self._get_next_token()

            # Try to parse precedence
            if self.cur_tok.kind == TokenKind.NUMBER:
                prec = int(self.cur_tok.value)
                if not (0 < prec < 101):
                    raise ParseError(
                        f"Invalid precedence: {prec} (valid values are 1-100)",
                        self.cur_tok.position,
                    )
                self._get_next_token()

            # Add the new operator to our precedence table so we can properly
            # parse it.

            # previously used when operators were only a single character:
            # set_binop_info(name[-1], prec, Associativity.LEFT)

            set_binop_info(r_name, prec, Associativity.LEFT)

        self._match(TokenKind.PUNCTUATOR, Puncs.OPEN_PAREN)
        argnames = []
        varargname = None

        while not self._cur_tok_is_punctuator(Puncs.CLOSE_PAREN):
            position = self.cur_tok.position
            if self.cur_tok.value == Puncs.ASTERISK:
                self._get_next_token()
                varargname = self.cur_tok.value

                self._get_next_token()
                break

            identifier, avartype = self._parse_var_declaration()

            if self._cur_tok_is_operator(Ops.ASSIGN):
                self._get_next_token()
                default_value = self._parse_expression()
            else:
                default_value = None

            argnames.append(
                Variable(
                    position,
                    identifier,
                    avartype if avartype is not None else self.vartypes._DEFAULT_TYPE,
                    None,
                    default_value,
                )
            )

            if self._cur_tok_is_punctuator(Puncs.COMMA):
                self._get_next_token()

        self._match(TokenKind.PUNCTUATOR, Puncs.CLOSE_PAREN)

        # get variable type for func prototype
        # we need to re-use the type definition code

        if self._cur_tok_is_punctuator(Puncs.COLON):
            self._get_next_token()
            vartype = self._parse_vartype_expr()

        if name.startswith("binary") and len(argnames) != 2:
            raise ParseError(
                f"Expected binary operator to have two operands, got {len(argnames)} instead",
                self.cur_tok.position,
            )
        elif name.startswith("unary") and len(argnames) != 1:
            raise ParseError(
                f"Expected unary operator to have one operand, got {len(argnames)} instead",
                self.cur_tok.position,
            )

        return Prototype(
            start,
            name,
            argnames,
            name.startswith(("unary", "binary")),
            prec,
            vartype,
            extern,
            varargname,
        )

    def _parse_external(self):
        self._get_next_token()  # consume 'extern'
        return self._parse_prototype(extern=True)

        # TODO: how do we deal with externals that might have a namespace collision
        # with a builtin?
        # possibility:
        # extern "alias" convert()
        # or prefix external calls with $?

    def _parse_definition(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume 'def'
        proto = self._parse_prototype()

        if self.cur_tok.kind == TokenKind.PASS:
            self._get_next_token()
            return Function(start, proto, None)

        if self._cur_tok_is_punctuator(Puncs.OPEN_CURLY):
            expr = self._parse_do_expr()
        else:
            expr = self._parse_expression()

        return Function(start, proto, expr)

    def _parse_toplevel_expression(self):
        start = self.cur_tok.position
        expr = self._parse_expression()

        # Anonymous function
        return Function.Anonymous(start, expr, vartype=self.anon_vartype)
