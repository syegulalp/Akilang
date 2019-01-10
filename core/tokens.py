from enum import Enum, unique
from collections import namedtuple


@unique
class TokenKind(Enum):
    EOF = -1
    IDENTIFIER = -4
    NUMBER = -5
    STRING = -6
    PUNCTUATOR = -7
    OPERATOR = -10

    VARTYPE = -50

    # Keywords are less than -100

    PASS = -1001

    DEF = -1010

    BINARY = -1011
    UNARY = -1012

    EXTERN = -1020
    CONST = -1030
    UNI = -1040
    CLASS = -1041
    #META = -1042
    PRAGMA = -1043

    PTR = -1045

    UNSAFE = -1046
    RETURN = -1047
    BREAK = -1048
    VAR = -1050
    #LET = -1060
    WITH = -1110
    LOOP = -1115
    CONTINUE = -1116
    IF = -1200
    WHEN = -1250
    THEN = -1300
    ELSE = -1400
    TRY = -1410
    RAISE = -1415
    EXCEPT = -1420
    FINALLY = -1430
    ELIF = -1450
    FOR = -1500
    IN = -1600
    WHILE = -1650
    MATCH = -1660
    DEFAULT = -1665


ESCAPES = {
    'n': chr(10),
    'r': chr(13),
    "'": "'",
    '"': '"',
    '{': r'\{',
    '}': r'\}'
}

Token = namedtuple('Token', 'kind value vartype position')


class Puncs():
    OPEN_CURLY = "{"
    CLOSE_CURLY = "}"
    OPEN_PAREN = "("
    CLOSE_PAREN = ")"
    OPEN_BRACKET = "["
    CLOSE_BRACKET = "]"
    COMMA = ","
    COLON = ":"
    AT_SIGN = "@"
    HASH_SIGN = "#"
    PERIOD = '.'
    ASTERISK = '*'
    ALL = []


for k, v in Puncs.__dict__.items():
    if isinstance(v, str) and not k.startswith('__'):
        Puncs.ALL.append(v)


class Ops():
    ADD = '+'
    SUBTRACT = '-'
    MULTIPLY = '*'
    DIVIDE = '/'
    GREATER_THAN = '>'
    LESS_THAN = '<'
    GREATER_THAN_EQ = '>='
    LESS_THAN_EQ = '<='
    ASSIGN = '='
    EQ = '=='
    NEQ = '!='
    INCR = '+='
    DECR = '-='
    AND = 'and'
    B_AND = '&'
    OR = 'or'
    B_OR = "|"
    XOR = 'xor'
    NOT = 'not'
    NEG = '-'


OP_DUNDERS = {
    Ops.ADD: 'add',
}

# Note that we do NOT use Ops for actual LLVM ops.

Builtins = {
    # c_alloc/c_free are provided by platformlib
    'c_addr',    
    'c_data',
    'c_gep',
    'c_ref', 'c_deref',
    'c_size',
    'c_obj_alloc',
    'c_obj_free',
    'c_obj_ref', 'c_obj_deref',
    'c_ptr',
    'c_ptr_mem',
    'c_ptr_int',
    'c_ptr_math',
    'c_ptr_mod',
    'cast', 'convert',
    'print',
    'ord',
    'dummy',
    'box',
    'type',
    'objtype',
    'unbox',
    'call',
    'isinstance',
    'refcount'
}

Builtin = {
    'c_out': (
        ('*args'),
        ('end:str')
    )
}

Dunders = {
    'len',
    'index',
    'del'
}

# with these, we should check to see if there's a specific dunder implementation
# for that type -- if not, we might be able to do it by way of a generic
# codegen implementation that isn't type specific

Decorators = {
    'varfunc',
    'inline',
    'noinline',
    'nomod',
    'unsafe_req',
    'track'
}

decorator_collisions = (
    ('inline', 'noinline'),
    ('inline', 'varfunc'),
    ('nomod', 'varfunc')
)
