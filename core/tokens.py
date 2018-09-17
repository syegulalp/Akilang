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

    DEF = -1010

    BINARY = -1011
    UNARY = -1012

    EXTERN = -1020
    CONST = -1030
    UNI = -1040
    CLASS = -1041

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
    ELIF = -1401
    FOR = -1500
    IN = -1600
    WHILE = -1650
    MATCH = -1660
    DEFAULT = -1665


ESCAPES = {
    'n': chr(10),
    'r': chr(13),
    "'": "'",
    '"':'"',
    '{':r'\{',
    '}':r'\}'
}

PUNCTUATORS = r'()[]{},:@'
COMMENT = "#"

Token = namedtuple('Token', 'kind value vartype position')

Builtins = {
    'c_addr',
    # c_alloc/c_free are provided by core.stdlib.nt
    'c_array_ptr',
    'c_data',
    'c_ref', 'c_deref',
    'c_size', 
    'c_obj_alloc', 'c_obj_free',
    'c_obj_ref', 'c_obj_deref',    
    'c_obj_size',    
    'c_ptr',
    'c_ptr_math','c_ptr_mod',
    'cast', 'convert',
    'out',
    'dummy'
}

Dunders = {
    'len'
}

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
    ('nomod','varfunc')
)