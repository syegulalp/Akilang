from core.lexer import TokenKind
from core.ast_module import (
    Array, Const, Uni, String, Function, Prototype, Number,
    Variable, DEFAULT_TYPE, DEFAULT_PREC, Unary, Pragma
)
from core.operators import UNASSIGNED, set_binop_info, Associativity
from core.errors import ParseError

# pylint: disable=E1101


class Toplevel():
    def _parse_pragma_expr(self):
        start = self.cur_tok.position

        # first, consume "pragma"
        self._get_next_token()

        self._match(TokenKind.PUNCTUATOR, '{')

        pragmas = []

        while True:
            t = self._parse_expression()
            pragmas.append(t)
            if self._cur_tok_is_punctuator('}'):
                self._get_next_token()
                break

        return Pragma(start, pragmas)

    def _parse_var_declaration(self):
        '''
        Parse variable declarations in uni/var/const blocks.
        '''

        # Not used for variable *references*, which are a little different.
        # Doesn't yet handle initializer assignment because that's handled
        # differently in each case, but maybe later we can unify it

        # first, consume the name of the identifier

        self._compare(TokenKind.IDENTIFIER)
        self._check_builtins()
        name = self.cur_tok.value
        self._get_next_token()

        # check for a vartype

        if self._cur_tok_is_punctuator(':'):
            self._get_next_token()
            vartype = self._parse_vartype_expr()

        else:
            vartype = None

        # check for array declaration

        if self._cur_tok_is_punctuator('['):
            arr_start = self.cur_tok.position
            elements = self._parse_array_accessor()

            # I don't think we need to extract a pointer type here

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

        self._get_next_token()  # consume the 'uni'

        self._match(TokenKind.PUNCTUATOR, '{')

        vars = []

        # TODO: merge this code with parse_var eventually
        # right now we can't do this because of some subtle differences
        # between how const/uni and regular vars are processed

        while True:

            start = self.cur_tok.position

            name, vartype = self._parse_var_declaration()

            # Parse the optional initializer
            if self._cur_tok_is_operator('='):
                self._get_next_token()  # consume the '='
                init = self._parse_expression()
            else:
                init = None

            if isinstance(init, String):
                init.anonymous = False

            if const and init:
                if not hasattr(init, 'val'):

                    # if there's no constant value on the initializer,
                    # it's an expression, and so we need to
                    # JIT-compile the existing constants
                    # to compute the value of that expression

                    tt = []
                    for k, v in self.consts.items():
                        tt.append((k, None, v, v.position))
                    t = ast_type(self.cur_tok.position, tt)

                    # TODO: move the below into evaluator
                    # maybe as `._eval_value`?

                    # Evaluate the temporary AST with the unis/consts
                    self.evaluator.reset()
                    self.evaluator._eval_ast(t)

                    # Codegen a function that obtains the computed result
                    # for this constant
                    self.evaluator.codegen.generate_code(
                        Function.Anonymous(start, init))

                    # Extract the variable type of that function
                    r_type = self.evaluator.codegen.module.globals[
                        Prototype.anon_name(Prototype)
                    ].return_value.type

                    # Run the function with the proper return type
                    e = self.evaluator._eval_ast(
                        Function.Anonymous(start, init, vartype=r_type),
                        return_type=r_type.c_type
                    )

                    # Extract and assign the value
                    init = Number(start, e.value, e.ast.proto.vartype)
                    self.consts[name] = init

                else:
                    self.consts[name] = Number(start, init.val, init.vartype)

            # FIXME: Let's just append an actual Variable node, whatever it is
            # & look at how codegen works from this, modify appropriately
            vars.append((name, vartype, init, start))

            if self._cur_tok_is_punctuator(','):
                self._get_next_token()

            if self.cur_tok.kind in (TokenKind.IDENTIFIER, TokenKind.VARTYPE):
                continue

            elif self._cur_tok_is_punctuator('}'):
                self._get_next_token()
                self.expr_stack.pop()
                return ast_type(self.cur_tok.position, vars)

            else:
                raise ParseError(
                    f'Expected variable declaration but got "{self.cur_tok.value}" instead',
                    self.cur_tok.position)

    def _parse_expression(self):
        self.level += 1
        lhs = self._parse_primary()
        
        # Start with precedence 0 because we want to bind any operator to the
        # expression at this point.
        self.level -= 1

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
                    self.cur_tok.position)
            name = f'unary.{self.cur_tok.value}'
            r_name = self.cur_tok.value
            self._get_next_token()
        elif self.cur_tok.kind == TokenKind.BINARY:
            self._get_next_token()
            if self.cur_tok.kind not in (TokenKind.IDENTIFIER,
                                         TokenKind.OPERATOR):
                raise ParseError(
                    f'Expected identifier or unassigned operator after "binary", got {self.cur_tok.value} instead',
                    self.cur_tok.position)
            name = f'binary.{self.cur_tok.value}'
            r_name = self.cur_tok.value
            self._get_next_token()

            # Try to parse precedence
            if self.cur_tok.kind == TokenKind.NUMBER:
                prec = int(self.cur_tok.value)
                if not (0 < prec < 101):
                    raise ParseError(f'Invalid precedence: {prec} (valid values are 1-100)',
                                     self.cur_tok.position)
                self._get_next_token()

            # Add the new operator to our precedence table so we can properly
            # parse it.

            #set_binop_info(name[-1], prec, Associativity.LEFT)

            # we previously used the above when operators were only a single character

            set_binop_info(r_name, prec, Associativity.LEFT)

        self._match(TokenKind.PUNCTUATOR, '(')
        argnames = []
        varargname = None

        while not self._cur_tok_is_punctuator(')'):
            position = self.cur_tok.position
            if self.cur_tok.value == '*':
                self._get_next_token()
                varargname = self.cur_tok.value

                self._get_next_token()
                break

            identifier, avartype = self._parse_var_declaration()

            if self._cur_tok_is_operator('='):
                self._get_next_token()
                default_value = self._parse_expression()
            else:
                default_value = None

            argnames.append(
                Variable(
                    position,
                    identifier,
                    avartype if avartype is not None else DEFAULT_TYPE,
                    None,
                    default_value
                )
            )

            if self._cur_tok_is_punctuator(','):
                self._get_next_token()

        self._match(TokenKind.PUNCTUATOR, ')')

        # get variable type for func prototype
        # we need to re-use the type definition code

        if self._cur_tok_is_punctuator(':'):
            self._get_next_token()
            vartype = self._parse_vartype_expr()
            # self._get_next_token()

        if name.startswith('binary') and len(argnames) != 2:
            raise ParseError(f'Expected binary operator to have two operands, got {len(argnames)} instead',
                             self.cur_tok.position)
        elif name.startswith('unary') and len(argnames) != 1:
            raise ParseError(f'Expected unary operator to have one operand, got {len(argnames)} instead',
                             self.cur_tok.position)

        return Prototype(start, name, argnames,
                         name.startswith(('unary', 'binary')), prec, vartype,
                         extern, varargname)

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
        
        if self._cur_tok_is_punctuator('{'):
            expr = self._parse_do_expr()
        else:
            expr = self._parse_expression()

        return Function(start, proto, expr)

    def _parse_toplevel_expression(self):
        start = self.cur_tok.position
        expr = self._parse_expression()

        # Anonymous function
        return Function.Anonymous(start, expr, vartype=self.anon_vartype)
