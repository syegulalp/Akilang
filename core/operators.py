from collections import namedtuple
from enum import Enum, unique

from core.errors import ParseError
from core.tokens import Ops


@unique
class Associativity(Enum):
    UNDEFINED = 0
    LEFT = 1
    RIGHT = 2


BinOpInfo = namedtuple("BinOpInfo", ["precedence", "associativity"])

BUILTIN_OP = {
    Ops.ASSIGN: BinOpInfo(2, Associativity.RIGHT),
    Ops.EQ: BinOpInfo(10, Associativity.LEFT),
    Ops.INCR: BinOpInfo(10, Associativity.LEFT),
    Ops.DECR: BinOpInfo(10, Associativity.LEFT),
    Ops.NEQ: BinOpInfo(10, Associativity.LEFT),
    Ops.B_AND: BinOpInfo(20, Associativity.LEFT),
    Ops.AND: BinOpInfo(5, Associativity.LEFT),
    Ops.B_OR: BinOpInfo(20, Associativity.LEFT),
    Ops.OR: BinOpInfo(5, Associativity.LEFT),
    Ops.XOR: BinOpInfo(5, Associativity.LEFT),
    Ops.LESS_THAN: BinOpInfo(10, Associativity.LEFT),
    Ops.LESS_THAN_EQ: BinOpInfo(10, Associativity.LEFT),
    Ops.GREATER_THAN: BinOpInfo(10, Associativity.LEFT),
    Ops.GREATER_THAN_EQ: BinOpInfo(10, Associativity.LEFT),
    Ops.ADD: BinOpInfo(20, Associativity.LEFT),
    Ops.SUBTRACT: BinOpInfo(20, Associativity.LEFT),
    Ops.MULTIPLY: BinOpInfo(40, Associativity.LEFT),
    Ops.DIVIDE: BinOpInfo(40, Associativity.LEFT),
}

BUILTIN_UNARY_OP = {Ops.NOT, Ops.NEG}

UNASSIGNED = {"!", "$", "%", "`", "^", "\\"}

IN_PLACE_OPS = {Ops.INCR, Ops.DECR}

FALSE_BINOP_INFO = BinOpInfo(-1, Associativity.UNDEFINED)

# TODO: in the future, we'll need a fresh copy of each BUILTIN_OP dict
# for each module, but for now we can just use one main dict.
# It's unlikely we're going to restore custom operators anyway.

# def builtin_operators():
# return sorted(BUILTIN_OP.keys())

# _binop_map = dict(BUILTIN_OP)


def binop_info(tok):
    kind, value, _, position = tok
    try:
        # return _binop_map[value]
        return BUILTIN_OP[value]
    except KeyError:
        from core.lexer import TokenKind, Puncs

        if kind == TokenKind.PUNCTUATOR and value not in Puncs.ALL:
            raise ParseError(f'Undefined operator: "{value}"', position)
        # Return a false binop info that has no precedence
        return FALSE_BINOP_INFO


def set_binop_info(op, precedence, associativity):
    BUILTIN_OP[op] = BinOpInfo(precedence, associativity)
    # _binop_map[op] = BinOpInfo(precedence, associativity)
