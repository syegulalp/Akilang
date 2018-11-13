from core.tokens import TokenKind
from core.ast_module import (
    Variable, Call, Number, Break, Return, String, Match,
    Do, Var, While, If, When, Loop, Array, ArrayAccessor, Class, Const,
    Uni, With, Binary, Unary, DEFAULT_PREC, Prototype, Function, Number,
    VariableType, Unsafe, Continue, Try, Raise,
    Pass, FString
)
from core.vartypes import CustomType, ArrayClass
from core.errors import ParseError, CodegenWarning
from core.operators import binop_info, Associativity, set_binop_info, UNASSIGNED
from core.tokens import Builtins, Ops, Puncs

import re

# pylint: disable=E1101


class Expressions():
    def _parse_pass_expr(self):
        self._get_next_token()
        return Pass(self.cur_tok.position)

    def _parse_try_expr(self):
        start = self.cur_tok.position

        self._get_next_token()
        self._compare(TokenKind.PUNCTUATOR, Puncs.OPEN_CURLY)
        try_expr = self._parse_do_expr()

        self._match(TokenKind.EXCEPT)
        self._compare(TokenKind.PUNCTUATOR, Puncs.OPEN_CURLY)
        except_expr = self._parse_do_expr()

        try:
            self._compare(TokenKind.ELSE)
        except ParseError:
            return Try(start, try_expr, except_expr)

        self._match(TokenKind.ELSE)
        self._compare(TokenKind.PUNCTUATOR, Puncs.OPEN_CURLY)
        else_expr = self._parse_do_expr()

        try:
            self._compare(TokenKind.FINALLY)
        except ParseError:
            return Try(start, try_expr, except_expr, else_expr)

        self._match(TokenKind.FINALLY)
        self._compare(TokenKind.PUNCTUATOR, Puncs.OPEN_CURLY)
        else_expr = self._parse_do_expr()

        return Try(start, try_expr, except_expr, else_expr, finally_expr)

    def _parse_raise_expr(self):
        start = self.cur_tok.position
        self._get_next_token()
        body = self._parse_expression()
        return Raise(start, body)

    def _parse_modifiers(self, current):
        start = current.position
        id_name = getattr(current, 'name', None)
        toplevel = current

        while True:
            child = None

            if self._cur_tok_is_punctuator(Puncs.OPEN_BRACKET):
                child = self._parse_array_accessor()

            elif self._cur_tok_is_punctuator(Puncs.OPEN_PAREN):
                args = self._parse_argument_list()
                child = Call(
                    start, id_name, args,
                    self.cur_tok.vartype
                )

            elif self.cur_tok.value == Puncs.PERIOD:
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

        if id_name in Builtins:
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
        self._get_next_token()  # consume the Puncs.OPEN_PAREN
        expr = self._parse_expression()
        self._match(TokenKind.PUNCTUATOR, Puncs.CLOSE_PAREN)
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

        if self._cur_tok_is_punctuator(Puncs.OPEN_PAREN):
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

        if Puncs.OPEN_CURLY not in cur.value:
            return String(cur.position, cur.value)
        
        in_template = re.split(r'([{}])', cur.value)

        exprs = []
        escape = False
        open_br = False

        for n in in_template:
            if n == Puncs.OPEN_CURLY and not escape:
                open_br = True
                continue
            if n == Puncs.CLOSE_CURLY and not escape:
                open_br = False
                continue
            if open_br:
                local_parser = self.__class__()
                for x in local_parser.parse_single_expression(n):
                    exprs.append(x)
                continue
            
            escape = False
            if n and n[-1] == '\\':
                escape = True
                n = n[0:-1]
            
            n = n.replace(r'%', r'%%')

            exprs.append(
                String(cur.position, n)
            )

        # another way to do this:
        # keep count of how many actual unescaped {} we have
        # if that count is zero, return a regular string
        # if that count is nonzero, return an fstring
        # that way all the escaping can be performed at once?
        
        return FString(cur.position, exprs)

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

            arguments = []
            
            if not self._cur_tok_is_punctuator(Puncs.CLOSE_PAREN):
                self._get_next_token()
                while True:
                    n = self._parse_vartype_expr()
                    arguments.append(n)
                    if self._cur_tok_is_punctuator(Puncs.COMMA):
                        self._get_next_token()
                        continue
                    if self._cur_tok_is_punctuator(Puncs.CLOSE_PAREN):
                        break

                self._get_next_token()
                self._match(TokenKind.PUNCTUATOR, Puncs.COLON)
                func_type = self._parse_vartype_expr()
                vartype = vartype(func_type, arguments)
            else:
                return vartype

        else:
            self._get_next_token()

        if self._cur_tok_is_punctuator(Puncs.OPEN_BRACKET):
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
        self._match(TokenKind.PUNCTUATOR, Puncs.OPEN_PAREN)
        convert_from = self._parse_expression()
        self._match(TokenKind.PUNCTUATOR, Puncs.COMMA)
        # For builtins that take a vartype as an argument,
        # we need to use this for now
        convert_to = self._parse_standalone_vartype_expr()
        self._match(TokenKind.PUNCTUATOR, Puncs.CLOSE_PAREN)
        return Call(start, callee, [convert_from, convert_to])

    def _parse_match_expr(self):
        start = self.cur_tok.position
        self._get_next_token()
        cond_item = self._parse_identifier_expr()
        self._match(TokenKind.PUNCTUATOR, Puncs.OPEN_CURLY)
        match_list = []
        default = None
        while not self._cur_tok_is_punctuator(Puncs.CLOSE_CURLY):
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
                if not self._cur_tok_is_punctuator(Puncs.COMMA):
                    break
                self._get_next_token()
            self._match(TokenKind.PUNCTUATOR, Puncs.COLON)
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
            if self._cur_tok_is_punctuator(Puncs.CLOSE_CURLY):
                self._get_next_token()
                break
        #if len(expr_list) == 1:
            #return expr_list[0]
        return Do(start, expr_list)

    def _parse_class_expr(self):
        self._get_next_token()
        self._compare(TokenKind.IDENTIFIER)
        self._check_builtins()

        class_name = self.cur_tok.value
        self._get_next_token()

        self._match(TokenKind.PUNCTUATOR, Puncs.OPEN_CURLY)

        vars = {}
        var_id = 0

        while not self._cur_tok_is_punctuator(Puncs.CLOSE_CURLY):
            name, type = self._parse_var_declaration()
            vars[name] = {'type': type, 'id': var_id}
            if self._cur_tok_is_punctuator(Puncs.COMMA):
                self._get_next_token()
            var_id += 1

        types = []
        v_types = {}
        n = 0
        for k, v in vars.items():
            types.append(v['type'])
            v_types[k] = {'pos': n, 'type': v}
            n += 1

        vartype = CustomType(class_name, types, v_types)

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

            if self._cur_tok_is_operator(Ops.ASSIGN):
                self._get_next_token()
                init = self._parse_expression()

            if isinstance(init, String):
                init.anonymous = False

            vars.append(
                Variable(pos, name, vartype, None, init)
            )

            if not self._cur_tok_is_punctuator(Puncs.COMMA):
                break

            self._match(TokenKind.PUNCTUATOR, Puncs.COMMA)

        return Var(var_pos, vars)

    def _parse_while_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'while'

        self.expr_stack.append(self._parse_while_expr)
        cond_expr = self._parse_expression()
        self.expr_stack.pop()

        body = self._parse_expression()
        return While(start, cond_expr, body)

    def _parse_when_expr(self):
        return self._parse_if_expr(True)
    
    def _parse_if_expr(self, when_expr=False):
        if when_expr:
            ast_node = When
            action = self._parse_when_expr
        else:
            ast_node = If
            action = self._parse_if_expr

        start = self.cur_tok.position
        self._get_next_token()

        self.expr_stack.append(self._parse_if_expr)
        cond_expr = self._parse_expression()
        self.expr_stack.pop()

        self._match(TokenKind.THEN)
        then_expr = self._parse_expression()
        if self.cur_tok.kind == TokenKind.ELSE:
            self._get_next_token()
            else_expr = self._parse_expression()
        elif self.cur_tok.kind == TokenKind.ELIF:            
            else_expr = action()
        else:
            else_expr = None

        return ast_node(start, cond_expr, then_expr, else_expr)

    def _parse_loop_expr(self):
        start = self.cur_tok.position
        self._get_next_token()  # consume the 'loop'

        # Check if this is a manually exited loop with no parameters
        if self._cur_tok_is_punctuator(Puncs.OPEN_CURLY):
            body = self._parse_do_expr()
            return Loop(start, None, None, None, None, body)

        self._match(TokenKind.PUNCTUATOR, Puncs.OPEN_PAREN)

        var_pos = self.cur_tok.position

        id_name, vartype = self._parse_var_declaration()

        self._match(TokenKind.OPERATOR, Ops.ASSIGN)
        start_expr = self._parse_expression()

        self._match(TokenKind.PUNCTUATOR, Puncs.COMMA)

        end_expr = self._parse_expression()

        # The step part is optional
        if self._cur_tok_is_punctuator(Puncs.COMMA):
            self._get_next_token()
            step_expr = self._parse_expression()
        else:
            step_expr = None

        self._match(TokenKind.PUNCTUATOR, Puncs.CLOSE_PAREN)

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
