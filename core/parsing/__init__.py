from collections import namedtuple

from core.lexer import Lexer, TokenKind, Token
from core.ast_module import (
    Decorator, Variable, Call, Number, Break, Return, String, Match,
    Do, Var, While, If, When, Loop, Array, ArrayAccessor, Class, Const,
    Uni, With, Binary, Unary, DEFAULT_PREC, Prototype, Function, Number, VariableType, Unsafe,
    _ANONYMOUS
)

from core.vartypes import generate_vartypes
from core.errors import ParseError, CodegenWarning
from core.operators import binop_info, Associativity, set_binop_info, UNASSIGNED
from core.tokens import Builtins, Decorators, Dunders

from core.parsing.expressions import Expressions
from core.parsing.toplevel import Toplevel

PARSE_ACTIONS = {
    TokenKind.RETURN: 'return',
    TokenKind.IDENTIFIER: 'identifier',
    TokenKind.OPERATOR: 'unaryop',
    TokenKind.NUMBER: 'number',
    TokenKind.STRING: 'string',
    TokenKind.VAR: 'var',
    TokenKind.WITH: 'with',
    TokenKind.WHILE: 'while',
    TokenKind.IF: 'if',
    TokenKind.WHEN: 'when',
    TokenKind.MATCH: 'match',
    TokenKind.LOOP: 'loop',
    TokenKind.CONTINUE: 'continue',
    TokenKind.TRY: 'try',
    TokenKind.RAISE: 'raise',
    TokenKind.BREAK: 'break',
    TokenKind.UNSAFE: 'unsafe',
    TokenKind.VARTYPE: 'standalone_vartype'
}

# pylint: disable=E1101


class Parser(Expressions, Toplevel):
    '''
    Parser for the Akilang language.
    After the parser is created, invoke parse_toplevel multiple times to parse
    Akilang source into an AST.
    '''

    def __init__(self, anon_vartype=None):
        self.vartypes = generate_vartypes()
        if anon_vartype is None:
            self.anon_vartype = self.vartypes._DEFAULT_TYPE
        else:
            self.anon_vartype = anon_vartype
        self.token_generator = None
        self.cur_tok = None
        self.local_types = {}
        self.consts = {}
        self.level = 0
        self.top_return = False
        self.expr_stack = []
        from core import codexec
        self.evaluator = codexec.AkilangEvaluator()
        self.parse_actions = PARSE_ACTIONS

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
        elif self.cur_tok.kind == TokenKind.META:
            return self._parse_meta_expr()
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
        if self.cur_tok.value in self.vartypes:
            raise ParseError(
                f'"{self.cur_tok.value}" cannot be used as an identifier (variable type)',
                self.cur_tok.position)

    def _parse_argument_list(self, args_required=False):
        args = []
        self._get_next_token()
        while True:
            if self._cur_tok_is_punctuator(')'):
                break
            arg = self._parse_expression()
            args.append(arg)
            if not self._cur_tok_is_punctuator(','):
                break
            self._get_next_token()
        if args_required and len(args) == 0:
            raise ParseError(
                f'At least one argument is required',
                self.cur_tok.position
            )
        return args

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

    def _parse_primary(self):
        if self.top_return and self.level == 1:
            raise ParseError(
                f'Unreachable code found after top-level "return" in function body',
                self.cur_tok.position)

        if self._cur_tok_is_punctuator('('):
            return self._parse_paren_expr()
        elif self._cur_tok_is_punctuator('{'):
            return self._parse_do_expr()
        # elif self._cur_tok_is_punctuator('['):
        #     # XXX: inconsistent
        #     result =  self._parse_array_accessor()
        #     self._get_next_token()
        #     return result

        elif self.cur_tok.kind in self.parse_actions:
            return getattr(self,
                           f'_parse_{self.parse_actions[self.cur_tok.kind]}_expr'
                           )()
        elif self.cur_tok.kind == TokenKind.EOF:
            raise ParseError('Expression expected but reached end of code',
                             self.cur_tok.position)
        else:
            raise ParseError(
                f'Expression expected but met unknown token: "{self.cur_tok.value}"',
                self.cur_tok.position
            )

    def _parse_builtin(self, name):
        if name in ('cast', 'convert'):
            return getattr(self, f'_parse_{name}_expr')()

        start = self.cur_tok.position
        self._get_next_token()
        self._match(TokenKind.PUNCTUATOR, '(', consume=False)
        args = self._parse_argument_list()
        self._get_next_token()
        return Call(start, name, args)

    # TODO: eventually we will be able to recognize
    # vartypes as args without this kind of hackery

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
                #self._get_next_token()
                break
            else:
                raise ParseError('Unclosed array accessor',
                                 self.cur_tok.position)

        return ArrayAccessor(start, elements)

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
