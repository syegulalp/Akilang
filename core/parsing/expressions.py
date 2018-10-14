from core.tokens import TokenKind
from core.ast_module import (
    Variable, Call, Number, Break, Return, String, Match,
    Do, Var, While, If, When, Loop, Array, ArrayAccessor, Class, Const,
    Uni, With, Binary, Unary, DEFAULT_PREC, Prototype, Function, Number,
    VariableType, Unsafe, Continue, Try, Raise,
    Pass
)
#from core.vartypes import DEFAULT_TYPE, CustomClass, VarTypes, ArrayClass
from core.vartypes import CustomClass, ArrayClass
from core.errors import ParseError, CodegenWarning
from core.operators import binop_info, Associativity, set_binop_info, UNASSIGNED
from core.tokens import Builtins, Dunders

# pylint: disable=E1101


class Expressions():
    def _parse_pass_expr(self):
        self._get_next_token()
        return Pass(self.cur_tok.position)
    def _parse_try_expr(self):
        start = self.cur_tok.position

        self._get_next_token()
        self._compare(TokenKind.PUNCTUATOR, '{')
        try_expr = self._parse_do_expr()

        self._match(TokenKind.EXCEPT)
        self._compare(TokenKind.PUNCTUATOR, '{')
        except_expr = self._parse_do_expr()

        try:
            self._compare(TokenKind.ELSE)
        except ParseError:
            return Try(start, try_expr, except_expr)

        self._match(TokenKind.ELSE)
        self._compare(TokenKind.PUNCTUATOR, '{')
        else_expr = self._parse_do_expr()

        try:
            self._compare(TokenKind.FINALLY)
        except ParseError:
            return Try(start, try_expr, except_expr, else_expr)

        self._match(TokenKind.FINALLY)
        self._compare(TokenKind.PUNCTUATOR, '{')
        else_expr = self._parse_do_expr()

        return Try(start, try_expr, except_expr, else_expr, finally_expr)

    def _parse_raise_expr(self):
        start = self.cur_tok.position
        self._get_next_token()
        body = self._parse_expression()
        return Raise(start, body)

    def _parse_modifiers(self, current):
        start = current.position
        id_name = getattr(current,'name',None)
        toplevel = current
        
        while True:
            child = None

            if self._cur_tok_is_punctuator('['):
                child = self._parse_array_accessor()

            elif self._cur_tok_is_punctuator('('):
                args = self._parse_argument_list()
                child = Call(
                    start, id_name, args,
                    self.cur_tok.vartype
                )

            elif self.cur_tok.value == '.':
                self._get_next_token()
                child = Variable(start, self.cur_tok.value)

            if child:
                current.child = child
                current = current.child
                self._get_next_token()
                continue

            break

        return toplevel

    def _parse_identifier_expr(self):
        start = self.cur_tok.position
        id_name = self.cur_tok.value

        if id_name in Builtins: # or id_name in Dunders:
            return self._parse_builtin(id_name)

        if id_name in self.consts:
            self._get_next_token()
            return self.consts[id_name]

        self._get_next_token()
        result = Variable(start, id_name, self.cur_tok.vartype)
        result = self._parse_modifiers(result)
        return result

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
            args = self._parse_argument_list(True)
            self._get_next_token()
            return Call(
                pos,
                vartype.new_signature(),
                args, vartype
            )

        return VariableType(pos, vartype)

    def _parse_unsafe_expr(self):
        cur = self.cur_tok
        self._get_next_token()
        body = self._parse_expression()
        return Unsafe(cur, body)

    def _parse_with_expr(self):
        cur = self.cur_tok
        self._get_next_token()  # consume `with`

        if self.cur_tok.kind != TokenKind.VAR:
            raise ParseError(
                f'Invalid "with" expression', self.cur_tok.position
            )

        vars = self._parse_var_expr()
        body = self._parse_expression()
        return With(cur, vars, body)

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

        if self.cur_tok.value in self.vartypes:
            vartype = self.vartypes[self.cur_tok.value]

        elif self.cur_tok.value in self.local_types:
            vartype = self.local_types[self.cur_tok.value].vartype

        else:
            raise ParseError(
                f'Expected a variable type but got {self.cur_tok.value} instead',
                self.cur_tok.position
            )

        if isinstance(vartype, self.vartypes.func.__class__):
            self._get_next_token()
            self._match(TokenKind.PUNCTUATOR, '(')

            arguments = []
            while True:
                n = self._parse_vartype_expr()
                arguments.append(n)
                if self._cur_tok_is_punctuator(','):
                    self._get_next_token()
                    continue
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

    def _parse_continue_expr(self):
        start = self.cur_tok.position
        self._get_next_token()
        return Continue(start)

    _if_eq_checks = (
        _parse_if_expr,
        _parse_while_expr,
        _parse_when_expr

    )
