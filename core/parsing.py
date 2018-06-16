from collections import namedtuple

from core.lexer import Lexer, TokenKind, Token
from core.ast_module import (
    Decorator, Variable, Call, Number, Break, Return, String, Match,
    Do, Var, While, If, When, Loop, Array, ArrayAccessor, Class, Const,
    Uni, VarIn, Binary, Unary, DEFAULT_PREC, Prototype, Function, Number, VariableType,
    _ANONYMOUS
)
from core.vartypes import DEFAULT_TYPE, CustomClass, VarTypes, ArrayClass
from core.errors import ParseError, CodegenWarning
from core.operators import binop_info, Associativity, set_binop_info, UNASSIGNED


class Parser(object):
    '''
    Parser for the Akilang language.
    After the parser is created, invoke parse_toplevel multiple times to parse
    Akilang source into an AST.
    '''

    def __init__(self, anon_vartype=DEFAULT_TYPE):
        self.token_generator = None
        self.cur_tok = None
        self.local_types = {}
        self.consts = {}
        self.anon_vartype = anon_vartype
        self.level = 0
        self.top_return = False
        self.expr_stack = []
        from core import codexec
        self.evaluator = codexec.AkilangEvaluator()

    def parse_toplevel(self, buf):
        '''
        Parse the next top-level token into an AST node.
        '''
        return next(self.parse_generator(buf))

    def parse_generator(self, buf):
        '''
        Given a string, returns an AST node representing it.
        '''
        self.token_generator = Lexer(buf).tokens()
        self.cur_tok = None
        self._get_next_token()

        while self.cur_tok.kind != TokenKind.EOF:
            self.top_return = False
            yield self._generate_toplevel()

    def _generate_toplevel(self):
        if self.cur_tok.kind == TokenKind.EXTERN:
            return self._parse_external()
        elif self.cur_tok.kind == TokenKind.UNI:
            return self._parse_uni_expr()
        elif self.cur_tok.kind == TokenKind.CONST:
            return self._parse_uni_expr(True)
        elif self.cur_tok.kind == TokenKind.CLASS:
            return self._parse_class_expr()
        elif self.cur_tok.kind == TokenKind.DEF:
            return self._parse_definition()
        elif self._cur_tok_is_punctuator('@'):
            return self._parse_decorator()
        else:
            return self._parse_toplevel_expression()

    def _get_next_token(self):
        self.cur_tok = next(self.token_generator)

    def _match(self, expected_kind, expected_value=None, consume=True):
        '''
        Consume the current token; verify that it's of the expected kind.
        If expected_kind == TokenKind.OPERATOR, verify the operator's value.
        '''
        if self.cur_tok.kind != expected_kind or (
                expected_value and self.cur_tok.value != expected_value):
            val = expected_value if expected_value is not None else expected_kind
            raise ParseError(
                f'Expected "{val}" but got "{self.cur_tok.value}" instead',
                self.cur_tok.position)

        if consume:
            self._get_next_token()

    def _compare(self, expected_kind, expected_value=None):
        '''
        Similar to _match, but does not consume the token, just returns
        whether or not the token matches what's expected.
        '''
        return self._match(expected_kind, expected_value, consume=False)

    def _cur_tok_is_punctuator(self, punc):
        '''
        Query whether the current token is a specific punctuator.
        '''
        return (self.cur_tok.kind == TokenKind.PUNCTUATOR
                and self.cur_tok.value == punc)

    def _cur_tok_is_operator(self, op):
        '''
        Query whether the current token is the operator op.
        '''
        return (self.cur_tok.kind == TokenKind.OPERATOR
                and self.cur_tok.value == op)

    def _check_builtins(self):
        '''
        Query whether the current token is either a builtin or a registered vartype.
        '''
        if self.cur_tok.value in Builtins:
            raise ParseError(
                f'"{self.cur_tok.value}" cannot be used as an identifier (builtin)',
                self.cur_tok.position)
        if self.cur_tok.value in VarTypes:
            raise ParseError(
                f'"{self.cur_tok.value}" cannot be used as an identifier (variable type)',
                self.cur_tok.position)

    def _parse_decorator(self):
        start = self.cur_tok.position
        self._get_next_token()
        dec_name = self._parse_identifier_expr()
        if dec_name.name not in Decorators:
            raise ParseError(
                f'Unknown decorator "{dec_name.name}"',
                start
            )
        if self._cur_tok_is_punctuator('{'):
            dec_body = []
            self._get_next_token()
            while True:
                dec_body.append(self._generate_toplevel())
                if self._cur_tok_is_punctuator('}'):
                    self._get_next_token()
                    break
        else:
            dec_body = [self._generate_toplevel()]
        return Decorator(start, dec_name, dec_body)

    def _parse_identifier_expr(self):
        start = self.cur_tok.position
        id_name = self.cur_tok.value

        if id_name in Builtins or id_name in Dunders:
            return self._parse_builtin(id_name)

        if id_name in self.consts:
            self._get_next_token()
            return self.consts[id_name]

        current = Variable(start, id_name, self.cur_tok.vartype)
        toplevel = current

        while True:
            self._get_next_token()

            if self._cur_tok_is_punctuator('['):
                current.child = self._parse_array_accessor()
                current = current.child
                continue

            elif self._cur_tok_is_punctuator('('):
                self._get_next_token()
                args = []
                if not self._cur_tok_is_punctuator(')'):
                    while True:
                        args.append(self._parse_expression())
                        if self._cur_tok_is_punctuator(')'):
                            break
                        self._match(TokenKind.PUNCTUATOR, ',')

                current.child = Call(start, id_name, args,
                                     self.cur_tok.vartype)
                current = current.child
                continue

            elif self.cur_tok.value == '.':
                self._get_next_token()
                current.child = Variable(start, self.cur_tok.value)
                current = current.child
                continue

            else:
                break

        return toplevel

    def _parse_number_expr(self):
        result = Number(self.cur_tok.position, self.cur_tok.value,
                        self.cur_tok.vartype)
        self._get_next_token()  # consume the number
        return result

    def _parse_paren_expr(self):
        self._get_next_token()  # consume the '('
        expr = self._parse_expression()
        self._match(TokenKind.PUNCTUATOR, ')')
        return expr

    def _parse_primary(self):

        if self.top_return and self.level == 1:
            raise ParseError(
                f'Unreachable code found after top-level "return" in function body',
                self.cur_tok.position)

        if self._cur_tok_is_punctuator('('):
            return self._parse_paren_expr()
        elif self._cur_tok_is_punctuator('{'):
            return self._parse_do_expr()
        elif self.cur_tok.kind == TokenKind.RETURN:
            return self._parse_return_expr()
        elif self.cur_tok.kind == TokenKind.IDENTIFIER:
            return self._parse_identifier_expr()
        elif self.cur_tok.kind == TokenKind.OPERATOR:
            return self._parse_unaryop_expr()
        elif self.cur_tok.kind == TokenKind.NUMBER:
            return self._parse_number_expr()
        elif self.cur_tok.kind == TokenKind.STRING:
            return self._parse_string_expr()
        elif self.cur_tok.kind == TokenKind.WHILE:
            return self._parse_while_expr()
        elif self.cur_tok.kind == TokenKind.IF:
            return self._parse_if_expr()
        elif self.cur_tok.kind == TokenKind.WHEN:
            return self._parse_when_expr()
        elif self.cur_tok.kind == TokenKind.LOOP:
            return self._parse_loop_expr()
        elif self.cur_tok.kind == TokenKind.VAR:
            return self._parse_var_expr()
        elif self.cur_tok.kind == TokenKind.WITH:
            return self._parse_with_expr()
        elif self.cur_tok.kind == TokenKind.MATCH:
            return self._parse_match_expr()
        elif self.cur_tok.kind == TokenKind.BREAK:
            return self._parse_break_expr()
        elif self.cur_tok.kind == TokenKind.VARTYPE:
            return self._parse_standalone_vartype_expr()

        elif self.cur_tok.kind == TokenKind.EOF:
            raise ParseError('Expression expected but reached end of code',
                             self.cur_tok.position)
        else:
            raise ParseError(
                f'Expression expected but met unknown token: "{self.cur_tok.value}"',
                self.cur_tok.position)

    def _parse_standalone_vartype_expr(self):
        '''
        Currently used for parsing variable types that are passed
        as an argument to a function. This is an exceptional case
        that will in time be eliminated.
        '''
        pos = self.cur_tok.position
        vartype = self._parse_vartype_expr()

        # if we're invoking a type as a call,
        # then we call the __new__ method
        # for that type

        if self._cur_tok_is_punctuator('('):
            args = []
            while True:
                arg = self._parse_expression()
                args.append(arg)
                if self._cur_tok_is_punctuator(','):
                    self._get_next_token()
                else:
                    break
            if vartype.is_obj_ptr():
                v=vartype.pointee
                v='.object.'+v.v_id
            else:
                v=vartype
                v=v.v_id
            return Call(pos, v+'.__new__', args)
        
        return VariableType(pos, vartype)

    def _parse_with_expr(self):
        cur = self.cur_tok
        self._get_next_token()  # consume `with`

        if self.cur_tok.kind != TokenKind.VAR:
            raise ParseError(
                f'Invalid "with" expression', self.cur_tok.position
            )

        vars = self._parse_var_expr()
        body = self._parse_expression()
        return VarIn(cur, vars, body)

    def _parse_break_expr(self):
        cur = self.cur_tok
        self._get_next_token()
        return Break(cur.position)

    def _parse_return_expr(self):
        self._get_next_token()
        cur = self.cur_tok
        val = self._parse_expression()
        if self.level == 1:
            self.top_return = True
        return Return(cur.position, val)

    def _parse_string_expr(self):
        cur = self.cur_tok
        self._get_next_token()
        return String(cur.position, cur.value)

    def _parse_vartype_expr(self):
        # This is an exception - it doesn't return an AST node,
        # but a variable type that is part of an AST node.

        is_ptr = 0

        while self.cur_tok.kind == TokenKind.PTR:
            is_ptr += 1
            self._get_next_token()

        if self.cur_tok.value in VarTypes:
            vartype = VarTypes[self.cur_tok.value]

        elif self.cur_tok.value in self.local_types:
            vartype = self.local_types[self.cur_tok.value].vartype

        else:
            raise ParseError(
                f'Expected a variable type but got {self.cur_tok.value} instead',
                self.cur_tok.position
            )

        if isinstance(vartype, VarTypes.func.__class__):
            self._get_next_token()
            self._match(TokenKind.PUNCTUATOR, '(')
            arguments = []
            while True:
                n = self._parse_vartype_expr()
                arguments.append(n)
                if self._cur_tok_is_punctuator(')'):
                    break
            self._get_next_token()
            self._match(TokenKind.PUNCTUATOR, ':')
            func_type = self._parse_vartype_expr()
            vartype = vartype(func_type, arguments)

        else:
            self._get_next_token()

        if self._cur_tok_is_punctuator('['):
            accessor = self._parse_array_accessor()

            fixed_size = True

            for n in accessor.elements:
                if isinstance(n, Variable):
                    fixed_size = False
                    break

            if not fixed_size:
                raise ParseError(
                    f'Array size cannot be set dynamically with a variable; use a constant',
                    n.position
                )

            # the array has to be built from the inside out
            # for n in reversed(accessor.elements):
                #vartype = VarTypes.array(vartype, int(n.val))

            elements = []
            for n in accessor.elements:
                elements.append(int(n.val))

            vartype = ArrayClass(vartype, elements)

            self._get_next_token()

        if vartype.is_obj:
            is_ptr += 1

        while is_ptr > 0:
            vartype = vartype.as_pointer(getattr(vartype, 'addrspace', 0))
            is_ptr -= 1

        return vartype

    def _parse_builtin(self, name):
        if name in ('cast', 'convert'):
            return getattr(self, f'_parse_{name}_expr')()
        start = self.cur_tok.position
        self._get_next_token()
        self._match(TokenKind.PUNCTUATOR, '(')
        args = []
        while True:
            expr = self._parse_expression()
            args.append(expr)
            if self._cur_tok_is_punctuator(','):
                self._get_next_token()
                continue
            if self._cur_tok_is_punctuator(')'):
                self._get_next_token()
                break
        return Call(start, name, args)

    # TODO: eventually we will be able to recognize
    # vartypes as args without this kind of hackery

    def _parse_cast_expr(self):
        return self._parse_convert_expr('cast')

    def _parse_convert_expr(self, callee='convert'):
        start = self.cur_tok.position
        self._get_next_token()
        self._match(TokenKind.PUNCTUATOR, '(')
        convert_from = self._parse_expression()
        self._match(TokenKind.PUNCTUATOR, ',')
        # For builtins that take a vartype as an argument,
        # we need to use this for now
        convert_to = self._parse_standalone_vartype_expr()
        #convert_to = self._parse_expression()
        self._match(TokenKind.PUNCTUATOR, ')')
        return Call(start, callee, [convert_from, convert_to])

    def _parse_match_expr(self):
        start = self.cur_tok.position
        self._get_next_token()
        cond_item = self._parse_identifier_expr()
        self._match(TokenKind.PUNCTUATOR, '{')
        match_list = []
        default = None
        while not self._cur_tok_is_punctuator('}'):
            set_default = False
            value_list = []
            while True:
                if self.cur_tok.kind == TokenKind.DEFAULT:
                    if default is not None:
                        raise ParseError(
                            '"default" keyword specified multiple times in "match" statement',
                            self.cur_tok.position)
                    set_default = True
                    self._get_next_token()
                    break
                value = self._parse_expression()
                value_list.append(value)
                if not self._cur_tok_is_punctuator(','):
                    break
                self._get_next_token()
            self._match(TokenKind.PUNCTUATOR, ':')
            expression = self._parse_expression()
            if set_default:
                default = expression
                continue
            for n in value_list:
                match_list.append((n, expression))

        self._get_next_token()
        return Match(start, cond_item, match_list, default)

    def _parse_do_expr(self):
        self._get_next_token()
        expr_list = []
        start = self.cur_tok.position
        while True:
            next_expr = self._parse_expression()
            expr_list.append(next_expr)
            if self._cur_tok_is_punctuator('}'):
                self._get_next_token()
                break
        if len(expr_list) == 1:
            return expr_list[0]
        return Do(start, expr_list)

    def _parse_class_expr(self):
        self._get_next_token()
        self._compare(TokenKind.IDENTIFIER)
        self._check_builtins()

        class_name = self.cur_tok.value
        self._get_next_token()

        self._match(TokenKind.PUNCTUATOR, '{')

        vars = {}
        var_id = 0

        while not self._cur_tok_is_punctuator('}'):
            name, type = self._parse_var_declaration()
            vars[name] = {'type': type, 'id': var_id}
            if self._cur_tok_is_punctuator(','):
                self._get_next_token()
            var_id += 1

        types = []
        v_types = {}
        n = 0
        for k, v in vars.items():
            types.append(v['type'])
            v_types[k] = {'pos': n, 'type': v}
            n += 1

        vartype = CustomClass(class_name, types, v_types)

        new_class = Class(class_name, vars, vartype)

        self.local_types[class_name] = new_class
        self._get_next_token()

        return new_class

    def _parse_var_expr(self):
        self._get_next_token()
        self._compare(TokenKind.IDENTIFIER)

        var_pos = self.cur_tok.position
        vars = []

        while True:
            init = None
            pos = self.cur_tok.position

            name, vartype = self._parse_var_declaration()

            if self._cur_tok_is_operator('='):
                self._get_next_token()
                init = self._parse_expression()

            if isinstance(init, String):
                init.anonymous = False

            vars.append(
                Variable(pos, name, vartype, None, init)
            )

            if not self._cur_tok_is_punctuator(','):
                break

            self._match(TokenKind.PUNCTUATOR, ',')

        return Var(var_pos, vars)

    def _parse_while_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'while'

        self.expr_stack.append(self._parse_while_expr)
        cond_expr = self._parse_expression()
        self.expr_stack.pop()

        body = self._parse_expression()
        return While(start, cond_expr, body)

    def _parse_if_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'if'

        self.expr_stack.append(self._parse_if_expr)
        cond_expr = self._parse_expression()
        self.expr_stack.pop()

        self._match(TokenKind.THEN)
        then_expr = self._parse_expression()
        if self.cur_tok.kind == TokenKind.ELSE:
            self._get_next_token()
            else_expr = self._parse_expression()
        elif self.cur_tok.kind == TokenKind.ELIF:
            else_expr = self._parse_if_expr()
        else:
            else_expr = None

        return If(start, cond_expr, then_expr, else_expr)

    # TODO: merge with _parse_if_expr

    def _parse_when_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'when'

        self.expr_stack.append(self._parse_when_expr)
        cond_expr = self._parse_expression()
        self.expr_stack.pop()

        self._match(TokenKind.THEN)
        then_expr = self._parse_expression()
        if self.cur_tok.kind == TokenKind.ELSE:
            self._get_next_token()
            else_expr = self._parse_expression()
        elif self.cur_tok.kind == TokenKind.ELIF:
            else_expr = self._parse_when_expr()
        else:
            else_expr = None

        return When(start, cond_expr, then_expr, else_expr)

    def _parse_loop_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'loop'

        # Check if this is a manually exited loop with no parameters
        if self._cur_tok_is_punctuator('{'):
            body = self._parse_do_expr()
            return Loop(start, None, None, None, None, body)

        self._match(TokenKind.PUNCTUATOR, '(')

        var_pos = self.cur_tok.position

        id_name, vartype = self._parse_var_declaration()

        self._match(TokenKind.OPERATOR, '=')
        start_expr = self._parse_expression()

        self._match(TokenKind.PUNCTUATOR, ',')

        end_expr = self._parse_expression()

        # The step part is optional
        if self._cur_tok_is_punctuator(','):
            self._get_next_token()
            step_expr = self._parse_expression()
        else:
            step_expr = None

        self._match(TokenKind.PUNCTUATOR, ')')

        body = self._parse_expression()

        loop_var = Variable(var_pos, id_name, vartype, None, start_expr)

        return Loop(start, id_name, loop_var, end_expr, step_expr, body)

    def _parse_array_accessor(self):
        self._match(TokenKind.PUNCTUATOR, '[')

        start = self.cur_tok.position
        elements = []

        while True:
            dimension = self._parse_expression()
            if hasattr(dimension, 'val'):
                dimension.val = int(dimension.val)
            elements.append(dimension)
            if self._cur_tok_is_punctuator(','):
                self._get_next_token()
                continue
            elif self._cur_tok_is_punctuator(']'):
                break
            else:
                raise ParseError('Unclosed array accessor',
                                 self.cur_tok.position)

        return ArrayAccessor(start, elements)

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

                    # Evaluate the temporary AST with the unis/consts
                    self.evaluator.reset()
                    self.evaluator._eval_ast(t)

                    # Codegen a function that obtains the computed result
                    # for this constant
                    self.evaluator.codegen.generate_code(
                        Function.Anonymous(start, init))

                    # Extract the variable type of that function
                    r_type = self.evaluator.codegen.module.globals[Prototype.anon_name(
                        Prototype)].return_value.type

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

    def _parse_binop_rhs(self, expr_prec, lhs):
        '''
        Parse the right-hand-side of a binary expression.
        expr_prec: minimal precedence to keep going (precedence climbing).
        lhs: AST of the left-hand-side.
        '''

        start = self.cur_tok.position
        while True:

            # possible loop for checking multi-token operators:
            # 1) take first operator token
            # 2) check it against the full list of tokens
            # 3) if there is more than one match, get the next token
            # otherwise, that's our token
            # 4) if the next token isn't an operator, fail
            # 5) get the association for the completed token

            cur_prec, _ = binop_info(self.cur_tok)
            # _ = cur_assoc
            # If this is a binary operator with precedence lower than the
            # currently parsed sub-expression, bail out. If it binds at least
            # as tightly, keep going.
            # Note that the precedence of non-operators is defined to be -1,
            # so this condition handles cases when the expression ended.
            if cur_prec < expr_prec:
                return lhs

            # This is where we need to test for the presence of
            # multi-token operators

            op = self.cur_tok.value
            self._get_next_token()  # consume the operator
            rhs = self._parse_primary()

            next_prec, next_assoc = binop_info(self.cur_tok)
            # There are four options:
            # 1. next_prec > cur_prec: we need to make a recursive call
            # 2. next_prec == cur_prec and operator is left-associative:
            #    no need for a recursive call, the next
            #    iteration of this loop will handle it.
            # 3. next_prec == cur_prec and operator is right-associative:
            #    make a recursive call
            # 4. next_prec < cur_prec: no need for a recursive call, combine
            #    lhs and the next iteration will immediately bail out.
            if cur_prec < next_prec:
                rhs = self._parse_binop_rhs(cur_prec + 1, rhs)

            if cur_prec == next_prec and next_assoc == Associativity.RIGHT:
                rhs = self._parse_binop_rhs(cur_prec, rhs)

            # If we're currently in an `if` or `while` clause
            # warn if we're using `=` in the clause instead of `==`

            if op == '=':
                try:
                    _ = self.expr_stack[-1].__func__
                except IndexError:
                    pass
                else:
                    if _ in self._if_eq_checks:
                        print(CodegenWarning(
                            f'possible confusion of assignment operator ("=") and equality test ("==") detected',
                            start))

            # Merge lhs/rhs
            lhs = Binary(start, op, lhs, rhs)

    def _parse_expression(self):
        self.level += 1
        lhs = self._parse_primary()
        # Start with precedence 0 because we want to bind any operator to the
        # expression at this point.
        self.level -= 1

        # constant folding goes here?
        # if lhs = constant or uni
        # & rhs = constant or uni
        # then substitute the constants
        # run the result through the compiler in its own instance
        # return a static expression
        # var x=1,y=2 in (x+y)

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

        if self.cur_tok.kind == TokenKind.IDENTIFIER:
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

        while not self._cur_tok_is_punctuator(')'):
            position = self.cur_tok.position
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
                         extern)

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

    _if_eq_checks = (
        _parse_if_expr,
        _parse_while_expr,
        _parse_when_expr
    )


# Maps builtins to functions. Builtins do not have their own tokens,
# they're just identifiers, but we need to reserve codegens for them.
# Eventually we'll want to move them into the pregenned stdlib somehow.

Builtins = {
    'c_ref', 'c_deref',
    'c_size', 'c_addr',
    'c_obj_ref', 'c_obj_deref',
    'c_obj_alloc', 'c_obj_free',
    'c_obj_size',
    'c_data', 'c_array_ptr',
    'cast', 'convert',
    'dummy',
}

Dunders = {
    'len'
}

Decorators = {
    'varfunc',
    'inline',
    'noinline'
}

decorator_collisions = (
    ('inline', 'noinline'),
    ('inline', 'varfunc')
)

# if __name__ == '__main__':
#     ast = Parser().parse_toplevel('def foo(x) 1 + bar(x)')
#     print(ast.flatten())
