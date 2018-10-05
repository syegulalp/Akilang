from collections import namedtuple
from enum import Enum, unique

from core.errors import ParseError


@unique
class Associativity(Enum):
    UNDEFINED = 0
    LEFT = 1
    RIGHT = 2


BinOpInfo = namedtuple('BinOpInfo', ['precedence', 'associativity'])

BUILTIN_OP = {
    '=': BinOpInfo(2, Associativity.RIGHT),
    '==': BinOpInfo(10, Associativity.LEFT),
    '+=': BinOpInfo(10, Associativity.LEFT),
    '-=': BinOpInfo(10, Associativity.LEFT),
    '!=': BinOpInfo(10, Associativity.LEFT),
    'and': BinOpInfo(5, Associativity.LEFT),
    'or': BinOpInfo(5, Associativity.LEFT),
    'xor': BinOpInfo(5, Associativity.LEFT),
    '<': BinOpInfo(10, Associativity.LEFT),
    '<=': BinOpInfo(10, Associativity.LEFT),
    '>': BinOpInfo(10, Associativity.LEFT),
    '>=': BinOpInfo(10, Associativity.LEFT),
    '+': BinOpInfo(20, Associativity.LEFT),
    '-': BinOpInfo(20, Associativity.LEFT),
    '*': BinOpInfo(40, Associativity.LEFT),
    '/': BinOpInfo(40, Associativity.LEFT),
}

BUILTIN_UNARY_OP = {
    'not',
    '-'
}

UNASSIGNED = {
    '!', '$', '%', '`', '^', '&', '|', '\','
}

FALSE_BINOP_INFO = BinOpInfo(-1, Associativity.UNDEFINED)


def builtin_operators():
    return sorted(BUILTIN_OP.keys())


_binop_map = dict(BUILTIN_OP)


def binop_info(tok):
    kind, value, _, position = tok
    try:
        return _binop_map[value]
    except KeyError:
        from core.lexer import TokenKind, PUNCTUATORS
        if kind == TokenKind.PUNCTUATOR and value not in PUNCTUATORS:
            raise ParseError(f'Undefined operator: "{value}"', position)
        # Return a false binop info that has no precedence
        return FALSE_BINOP_INFO


def set_binop_info(op, precedence, associativity):
    _binop_map[op] = BinOpInfo(precedence, associativity)
