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
        LPAREN,
        RPAREN,
        COMMA,
        DOT,
        SEMI,
        TEXT1,
        TEXT2,
        HEX,
        COLON,
        LBRACE,
        RBRACE,
        LBRACKET,
        RBRACKET,
        QUOTE,
        APOST,
        BACKQUOTE,
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
        LSHIFT,
        RSHIFT,
        BIN_AND,
        BIN_OR,
        ASSIGN,
        DEF,
        EXTERN,
        VAR,
        IF,
        WHEN,
        ELSE,
        LOOP,
        BREAK,
        WITH,
        PTR,
        FUNC,
        TRUE,
        FALSE,
        NONE,
        UNSAFE,
    }

    ignore = " \t"

    # Tokens
    TEXT1 = r"'(?:[^'\\]|\\.)*'"
    TEXT2 = r'"(?:[^"\\]|\\.)*"'
    HEX = r"0[hx][a-fA-F0-9]*"
    NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
    NAME["def"] = DEF
    NAME["extern"] = EXTERN
    NAME["var"] = VAR
    NAME["and"] = AND
    NAME["or"] = OR
    NAME["not"] = NOT
    NAME["if"] = IF
    NAME["when"] = WHEN
    NAME["else"] = ELSE
    NAME["loop"] = LOOP
    NAME["break"] = BREAK
    NAME["with"] = WITH
    NAME["ptr"] = PTR
    NAME["func"] = FUNC
    NAME["True"] = TRUE
    NAME["False"] = FALSE
    NAME["None"] = NONE
    NAME["unsafe"] = UNSAFE

    INT_DIV = r"//"
    INCR = r"(\+\=)"
    DECR = r"(\-\=)"
    PLUS = r"\+"
    MINUS = r"\-"
    TIMES = r"\*"
    DIV = r"\/"
    LBRACKET = r"\["
    RBRACKET = r"\]"
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
    LSHIFT = r"\<\<"
    RSHIFT = r"\>\>"
    ASSIGN = r"\="
    BIN_AND = r"\&"
    BIN_OR = r"\|"
    QUOTE = r"\""
    APOST = r"\'"
    BACKQUOTE = r"\`"
    DOT = r"\."
    SEMI = r"\;"

    def tokenize(self, text):
        self.text = text
        self.lineno = 1
        return super().tokenize(text)

    @_(r"\d+[.]\d+")
    def FLOAT(self, t):
        t.value = float(t.value)
        return t

    @_(r"\d+")
    def INTEGER(self, t):
        t.value = int(t.value)
        return t

    @_(r"\#[^\n]*[\n$]*")
    def comment(self, t):
        self.lineno += t.value.count("\n")

    @_(r"\n+")
    def newline(self, t):
        self.lineno += t.value.count("\n")

    def error(self, t):
        raise AkiSyntaxErr(Pos(self), self.text, f'Illegal character "{t.value[0]}"')

_AkiLexer = AkiLexer()