from sly import Lexer
from core.error import AkiSyntaxErr


class Pos:
    def __init__(self, p):
        try:
            self.lineno = p.lineno
        except (KeyError, AttributeError):
            self.lineno = 1

        try:
            self.index = p.index
        except (KeyError, AttributeError):
            self.index = 0


class AkiLexer(Lexer):
    tokens = {
        NAME,
        INTEGER,
        FLOAT,
        INT_DIV,
        INCR,
        DECR,
        PLUS,
        MINUS,
        TIMES,
        DIV,
        EQ,
        NEQ,
        LEQ,
        GEQ,
        LT,
        GT,
        AND,
        OR,
        NOT,
        BIN_AND,
        BIN_OR,
        ASSIGN,
        LPAREN,
        RPAREN,
        COMMA,
        COLON,
        LBRACE,
        RBRACE,
        DEF,
        VAR,
        IF,
        WHEN,
        ELSE,
        LOOP,
        BREAK,
    }

    ignore = " \t"

    # Tokens
    NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
    NAME["def"] = DEF
    NAME["var"] = VAR
    NAME["and"] = AND
    NAME["or"] = OR
    NAME["not"] = NOT
    NAME["if"] = IF
    NAME["when"] = WHEN
    NAME["else"] = ELSE
    NAME["loop"] = LOOP
    NAME["break"] = BREAK

    INT_DIV = r"//"

    INCR = r"(\+\=)"

    DECR = r"(\-\=)"

    PLUS = r"\+"
    MINUS = r"\-"
    TIMES = r"\*"
    DIV = r"\/"
    LPAREN = r"\("
    RPAREN = r"\)"
    COMMA = r"\,"
    COLON = r"\:"
    LBRACE = r"\{"
    RBRACE = r"\}"
    EQ = r"\=\="
    NEQ = r"\!\="
    LEQ = r"\<\="
    GEQ = r"\>\="
    LT = r"\<"
    GT = r"\>"
    ASSIGN = r"\="
    BIN_AND = r"\&"
    BIN_OR = r"\|"

    def tokenize(self, text):
        self.text = text
        self.lineno = 1
        return super().tokenize(text)

    @_(r"\d?[.]\d+")
    def FLOAT(self, t):
        t.value = float(t.value)
        return t

    @_(r"\d+")
    def INTEGER(self, t):
        t.value = int(t.value)
        return t

    @_(r"\n+")
    def newline(self, t):
        self.lineno += t.value.count(r"\n")

    def error(self, t):
        raise AkiSyntaxErr(Pos(self), self.text, f'Illegal character "{t.value[0]}"')

