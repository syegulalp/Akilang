from core.repl import RED, REP, CMD, MAG


class ReloadException(Exception):
    """
    Used to signal that the REPL needs to reload.
    """
    pass


class QuitException(Exception):
    """
    Used to signal the REPL is quitting normally.
    """
    pass


class LocalException(Exception):
    """
    Used for control flow in functions.
    """
    pass


class AkiBaseErr(Exception):
    """
    Base Aki error type. This should not be used directly.
    """
    _errtype = "0 (General error)"

    def __init__(self, p, txt, msg):
        if p is None:
            self.lineno = 1
            self.col = 1
            self.msg = msg
            self.extract = txt
            return
        
        self.msg = msg
        self.p = p
        last_newline = txt.rfind(f"\n", 0, self.p.index)

        if last_newline == -1:
            last_newline = 0
            self.col = self.p.index + 1
        else:
            self.col = self.p.index - last_newline

        end = txt.find(f"\n", self.p.index + 1)
        if end == -1:
            self.extract = txt[last_newline:]
        else:
            self.extract = txt[last_newline:end]

        self.lineno = self.p.lineno

    def __str__(self):
        return f"{'-'*40}\n{RED}Error: {self._errtype}\n{REP}Line {self.lineno}:{self.col}\n{self.msg}\n{'-'*40}\n{CMD}{self.extract}\n{MAG}{'-'*(self.col-1)}^{REP}"


class AkiSyntaxErr(AkiBaseErr):
    """
    Thrown when we encounter syntax or parsing issues.
    """
    _errtype = "1 (Syntax error)"


class AkiNameErr(AkiBaseErr):
    """
    Thrown when a name reference is not recognized.
    """
    _errtype = "2 (Name error)"


class AkiTypeErr(AkiBaseErr):
    """
    Thrown when types are not compatible or other type-related errors arise.
    """
    _errtype = "3 (Type error)"


class AkiOpError(AkiBaseErr):
    """
    Thrown when the op for a function does not exist or is incompatible.
    """
    _errtype = "4 (Operator error)"
