from lexer import *
from ast_module import *
from collections import namedtuple
from vartypes import DEFAULT_TYPE, CustomClass
from errors import ParseError
from operators import *


class Parser(object):
    """Parser for the Akilang language.
    After the parser is created, invoke parse_toplevel multiple times to parse
    Akilang source into an AST.
    """

    def __init__(self, anon_vartype=DEFAULT_TYPE):
        self.token_generator = None
        self.cur_tok = None
        self.local_types = {}
        self.anon_vartype = anon_vartype
        self.level = 0
        self.top_return = False

    # toplevel ::= definition | external | expression
    def parse_toplevel(self, buf):
        return next(self.parse_generator(buf))

    def parse_generator(self, buf):
        """Given a string, returns an AST node representing it."""
        self.token_generator = Lexer(buf).tokens()
        self.cur_tok = None
        self._get_next_token()

        # For the time being we're keeping this and the other
        # major elif chain as-is, because we need to have the
        # priority of the options enforced

        while self.cur_tok.kind != TokenKind.EOF:
            self.top_return = False

            if self.cur_tok.kind == TokenKind.EXTERN:
                yield self._parse_external()
            elif self.cur_tok.kind == TokenKind.UNI:
                yield self._parse_uni_expr()
            elif self.cur_tok.kind == TokenKind.CONST:
                yield self._parse_uni_expr(True)
            elif self.cur_tok.kind == TokenKind.CLASS:
                yield self._parse_class_expr()
            elif self.cur_tok.kind == TokenKind.DEF:
                yield self._parse_definition()
            else:
                yield self._parse_toplevel_expression()

    def _get_next_token(self):
        self.cur_tok = next(self.token_generator)

    def _match(self, expected_kind, expected_value=None):
        """Consume the current token; verify that it's of the expected kind.
        If expected_kind == TokenKind.OPERATOR, verify the operator's value.
        """
        if self.cur_tok.kind != expected_kind or (
                expected_value and self.cur_tok.value != expected_value):
            raise ParseError(
                f'Expected "{expected_value}" but got "{self.cur_tok.value}"',
                self.cur_tok.position)

        self._get_next_token()

    def _cur_tok_is_punctuator(self, punc):
        return (self.cur_tok.kind == TokenKind.PUNCTUATOR
                and self.cur_tok.value == punc)

    def _cur_tok_is_operator(self, op):
        """Query whether the current token is the operator op"""
        return (self.cur_tok.kind == TokenKind.OPERATOR
                and self.cur_tok.value == op)

    # identifierexpr
    #   ::= identifier
    #   ::= identifier '(' expression* ')'
    #   ::= identifier '[' accessor ']'
    def _parse_identifier_expr(self):
        start = self.cur_tok.position
        id_name = self.cur_tok.value

        # TODO: builtins will also need to be reworked
        if id_name in Builtins:
            return self._parse_builtin(id_name)

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

                if toplevel==current:
                    current = Call(start, id_name, args, self.cur_tok.vartype)
                    toplevel = current
                else:
                    current.child = Call(start, id_name, args, self.cur_tok.vartype)
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

    # numberexpr ::= number

    def _parse_number_expr(self):
        result = Number(self.cur_tok.position, self.cur_tok.value,
                        self.cur_tok.vartype)
        self._get_next_token()  # consume the number
        return result

    # parenexpr ::= '(' expression ')'

    def _parse_paren_expr(self):
        self._get_next_token()  # consume the '('
        expr = self._parse_expression()
        self._match(TokenKind.PUNCTUATOR, ')')
        return expr

    # primary
    #   ::= identifierexpr
    #   ::= numberexpr
    #   ::= parenexpr
    #   ::= ifexpr
    #   ::= forexpr
    #   ::= unaryexpr

    PUNCTUATORS = '()[]{};,:'

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
        elif self.cur_tok.kind == TokenKind.LET:
            return self._parse_let_expr()
        elif self.cur_tok.kind == TokenKind.MATCH:
            return self._parse_match_expr()
        elif self.cur_tok.kind == TokenKind.BREAK:
            return self._parse_break_expr()

        elif self.cur_tok.kind == TokenKind.EOF:
            raise ParseError('Expression expected but reached end of code',
                             self.cur_tok.position)
        else:
            raise ParseError(
                f'Expression expected but met unknown token: "{self.cur_tok.value}"',
                self.cur_tok.position)

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
            raise ParseError(f'expected a variable type',
                             self.cur_tok.position)

        if self._cur_tok_is_punctuator('['):
            accessor = self._parse_array_accessor()
            for n in accessor.elements:
                vartype = VarTypes.array(vartype, int(n.val))
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
        self._get_next_token()
        convert_to = self._parse_vartype_expr()
        self._get_next_token()
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

        if self.cur_tok.kind != TokenKind.IDENTIFIER:
            raise ParseError(
                f'expected identifier after "let", not "{self.cur_tok.value}"',
                self.cur_tok.position)

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

    # letexpr ::= 'let' ( identifier ('=' expr)? )
    def _parse_let_expr(self):
        self._get_next_token()  # consume the 'let'
        let_pos = self.cur_tok.position
        vars = []

        if self.cur_tok.kind != TokenKind.IDENTIFIER:
            raise ParseError(
                f'expected identifier after "let", not "{self.cur_tok.value}"',
                self.cur_tok.position)

        while True:
            init = None
            pos = self.cur_tok.position

            name, vartype = self._parse_var_declaration()

            if self._cur_tok_is_operator('='):
                self._get_next_token()
                init = self._parse_expression()

            vars.append((name, vartype, init, pos))
            if not self._cur_tok_is_punctuator(','):
                break
            
            self._match(TokenKind.PUNCTUATOR, ',')
            #self._get_next_token()

        return Let(let_pos, vars)

    # whileexpr :: = 'while' expr (expr)
    def _parse_while_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'while'
        cond_expr = self._parse_expression()
        body = self._parse_expression()
        return While(start, cond_expr, body)

    # ifexpr ::= 'if' expr 'then' expr 'else' expr
    def _parse_if_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'if'
        cond_expr = self._parse_expression()
        #self._match(TokenKind.PUNCTUATOR, ':')
        self._match(TokenKind.THEN)
        then_expr = self._parse_expression()
        if self.cur_tok.kind == TokenKind.ELSE:
            self._get_next_token()
            #self._match(TokenKind.PUNCTUATOR, ':')
            else_expr = self._parse_expression()
        elif self.cur_tok.kind == TokenKind.ELIF:
            else_expr = self._parse_if_expr()
        else:
            else_expr = None

        return If(start, cond_expr, then_expr, else_expr)

    # whenexpr ::= 'when' expr 'then' expr ('else' expr)?
    def _parse_when_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'when'
        cond_expr = self._parse_expression()
        self._match(TokenKind.PUNCTUATOR, ':')
        then_expr = self._parse_expression()
        if self.cur_tok.kind == TokenKind.ELSE:
            self._get_next_token()
            self._match(TokenKind.PUNCTUATOR, ':')
            else_expr = self._parse_expression()
        else:
            else_expr = None
        return When(start, cond_expr, then_expr, else_expr)

    # loopexpr ::= 'loop' ('(' identifier '=' expr ',' expr (',' expr)? ')')? expr

    def _parse_loop_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'loop'

        # Check if this is a manually exited loop with no parameters
        if self._cur_tok_is_punctuator('{'):
            body = self._parse_do_expr()
            return Loop(start, None, None, None, None, body)

        self._match(TokenKind.PUNCTUATOR, '(')
        id_name = self.cur_tok.value
        self._match(TokenKind.IDENTIFIER)
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
        return Loop(start, id_name, start_expr, end_expr, step_expr, body)

    def _parse_array_accessor(self):
        # TODO: replace "accessor" with "elements" or "dimensions"
        if not self._cur_tok_is_punctuator('['):
            raise ParseError('Improper array accessor', self.cur_tok.position)

        start = self.cur_tok.position
        elements = []

        while True:
            self._get_next_token()
            dimension = self._parse_expression()
            elements.append(dimension)
            if self._cur_tok_is_punctuator(','):
                continue

            elif self._cur_tok_is_punctuator(']'):
                break
            else:
                raise ParseError('Unclosed array accessor',
                                 self.cur_tok.position)

        return ArrayAccessor(start, elements)

    def _parse_var_declaration(self):
        # this is used to parse variable declarations in
        # uni, var, and const blocks.
        # It's not used for variable references, which are a little different.
        # it doesn't yet handle initializer assignment because that's handled
        # differently in each case, but maybe later we can unify it

        # first, consume the name of the identifier

        if not self.cur_tok.kind in (TokenKind.IDENTIFIER, ):
            raise ParseError(
                f'expected variable identifier, got "{self.cur_tok.value}" instead',
                self.cur_tok.position)

        name = self.cur_tok.value

        self._get_next_token()

        # check for a vartype

        if self._cur_tok_is_punctuator(':'):
            self._get_next_token()
            vartype = self._parse_vartype_expr()
            self._get_next_token()

        else:
            vartype = None

        # check for array declaration

        if self._cur_tok_is_punctuator('['):
            arr_start = self.cur_tok.position
            elements = self._parse_array_accessor()

            # if this is a pointer, go down one level

            oo=getattr(vartype,'pointee',None)
            if oo is not None:
                vartype=oo

            vartype = Array(arr_start, elements, vartype)
            self._get_next_token()

        return name, vartype

    def _parse_uni_expr(self, const=False):

        if const:
            ast_type = Const
        else:
            ast_type = Uni

        self._get_next_token()  # consume the 'uni'

        if not self._cur_tok_is_punctuator('{'):
            raise ParseError(
                f'expected "(" block declaration, not "{self.cur_tok.value}"',
                self.cur_tok.position)

        self._get_next_token()  # consume the '('
        vars = []

        # TODO: all of this should be moved into its own function
        # so it can be code-shared with var if possible

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

            vars.append((name, vartype, init, start))

            if self._cur_tok_is_punctuator(','):
                self._get_next_token()

            if self.cur_tok.kind in (TokenKind.IDENTIFIER, TokenKind.VARTYPE):
                continue

            elif self._cur_tok_is_punctuator('}'):
                self._get_next_token()
                return ast_type(self.cur_tok.position, vars)

            else:
                raise ParseError(
                    f'expected variable declaration, not "{self.cur_tok.value}"',
                    self.cur_tok.position)

    # varexpr ::= 'var' ( identifier ('=' expr)? )+ 'in' expr
    def _parse_var_expr(self):
        self._get_next_token()  # consume the 'var'
        vars = []

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

            vars.append((name, vartype, init, start))

            if self._cur_tok_is_punctuator(','):
                self._get_next_token()
                continue

            if self.cur_tok.kind == TokenKind.IN:
                self._get_next_token()
                body = self._parse_expression()
                return VarIn(self.cur_tok.position, vars, body)

            else:
                raise ParseError(
                    'expected variable declaration, "in" expression, or parenthetical "do" expression after "var"',
                    self.cur_tok.position)

    # binoprhs ::= (<binop> primary)*
    def _parse_binop_rhs(self, expr_prec, lhs):
        """Parse the right-hand-side of a binary expression.
        expr_prec: minimal precedence to keep going (precedence climbing).
        lhs: AST of the left-hand-side.
        """
        start = self.cur_tok.position
        while True:

            # possible loop for checking multi-token operators:
            # 1) take first operator token
            # 2) check it against the full list of tokens
            # 3) if there is more than one match, get the next token
            # otherwise, that's our token
            # 4) if the next token isn't an operator, fail
            # 5) get the association for the completed token

            cur_prec, cur_assoc = binop_info(self.cur_tok)
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

            # Merge lhs/rhs
            lhs = Binary(start, op, lhs, rhs)

    # expression ::= primary binoprhs
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

    # unary ::= op primary
    def _parse_unaryop_expr(self):
        start = self.cur_tok.position
        op = self.cur_tok.value
        self._get_next_token()
        rhs = self._parse_primary()
        return Unary(start, op, rhs)

    # prototype
    #   ::= id '(' id* ')'
    #   ::= 'binary' LETTER number? '(' id id ')'
    #   ::= 'unary' LETTER '(' id id ')'
    def _parse_prototype(self, extern=False):
        start = self.cur_tok.position
        prec = DEFAULT_PREC
        vartype = None  # DEFAULT_TYPE
        #is_ptr = False

        if self.cur_tok.kind == TokenKind.IDENTIFIER:
            if self.cur_tok.value in VarTypes:
                raise ParseError(
                    f'"{self.cur_tok.value}" is a reserved word and cannot be used as an identifier',
                    self.cur_tok.position)
            name = self.cur_tok.value
            r_name = name
            self._get_next_token()

        elif self.cur_tok.kind == TokenKind.UNARY:
            self._get_next_token()
            if self.cur_tok.kind not in (TokenKind.IDENTIFIER,
                                         TokenKind.OPERATOR):
                raise ParseError(
                    'Expected identifier or unassigned operator after "unary"',
                    self.cur_tok.position)
            name = f'unary.{self.cur_tok.value}'
            r_name = self.cur_tok.value
            self._get_next_token()
        elif self.cur_tok.kind == TokenKind.BINARY:
            self._get_next_token()
            if self.cur_tok.kind not in (TokenKind.IDENTIFIER,
                                         TokenKind.OPERATOR):
                raise ParseError(
                    'Expected identifier or unassigned operator after "binary"',
                    self.cur_tok.position)
            name = f'binary.{self.cur_tok.value}'
            r_name = self.cur_tok.value
            self._get_next_token()

            # Try to parse precedence
            if self.cur_tok.kind == TokenKind.NUMBER:
                prec = int(self.cur_tok.value)
                if not (0 < prec < 101):
                    raise ParseError(f'Invalid precedence: {prec}',
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
            #is_ptr = False
            identifier, avartype = self._parse_var_declaration()
            argnames.append((identifier, avartype
                             if avartype is not None else DEFAULT_TYPE))
            if self._cur_tok_is_punctuator(','):
                self._get_next_token()

        self._match(TokenKind.PUNCTUATOR, ')')

        # get variable type for func prototype
        # we need to re-use the type definition code

        if self._cur_tok_is_punctuator(':'):
            self._get_next_token()
            vartype = self._parse_vartype_expr()
            self._get_next_token()

        if name.startswith('binary') and len(argnames) != 2:
            raise ParseError('Expected binary operator to have 2 operands',
                             self.cur_tok.position)
        elif name.startswith('unary') and len(argnames) != 1:
            raise ParseError('Expected unary operator to have one operand',
                             self.cur_tok.position)

        return Prototype(start, name, argnames,
                         name.startswith(('unary', 'binary')), prec, vartype,
                         extern)

    # external ::= 'extern' prototype
    def _parse_external(self):
        self._get_next_token()  # consume 'extern'
        return self._parse_prototype(extern=True)

    # definition ::= 'def' prototype expression
    def _parse_definition(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume 'def'
        proto = self._parse_prototype()

        if self._cur_tok_is_punctuator('{'):
            expr = self._parse_do_expr()
        else:
            expr = self._parse_expression()

        return Function(start, proto, expr)

    # toplevel ::= expression
    def _parse_toplevel_expression(self):
        start = self.cur_tok.position
        expr = self._parse_expression()

        # Anonymous function
        return Function.Anonymous(start, expr, vartype=self.anon_vartype)


# Maps builtins to functions. Builtins do not have their own tokens,
# they're just identifiers, but we need to reserve codegens for them.
# Eventually we'll want to move them into the pregenned stdlib somehow.

Builtins = {
    'c_obj_ref', 'c_obj_deref', 'c_ref', 'c_size', 'c_array_ptr', 'c_deref',
    'cast', 'convert', 'c_addr'
}

#---- Some unit tests ----#


if __name__ == '__main__':

    ast = Parser().parse_toplevel('def foo(x) 1 + bar(x)')
    print(ast.flatten())

    # import aki
    # aki.run(parseonly=True)
