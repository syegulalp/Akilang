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

    def __init__(self, index, txt, msg):
        if txt is None:
            txt = ""

        if index is None:
            index = 1
        elif not isinstance(index, int):
            index = index.index
        elif index == 0:
            index = 1

        last_newline = txt.rfind(f"\n", 0, index)

        if last_newline == -1:
            last_newline = 0
            self.col = index
        else:
            self.col = index - last_newline

        end = txt.find(f"\n", index + 1)
        if end == -1:
            self.extract = txt[last_newline:]
        else:
            self.extract = txt[last_newline:end]

        if last_newline == 0:
            self.lineno = 1
        else:
            self.lineno = txt.count(f"\n", 0, last_newline + 1) + 1

        self.msg = msg

    def __str__(self):
        return f"{'-'*72}\n{RED}Error: {self._errtype}\n{REP}Line {self.lineno}:{self.col}\n{self.msg}\n{'-'*72}\n{CMD}{self.extract}\n{MAG}{'-'*(self.col-1)}^{REP}"


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
