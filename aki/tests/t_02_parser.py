# Test generation of all ASTs in parser.
# We might want to find a way to take the debug output from the parser,
# and use that to auto-generate this test suite.

import unittest
from core.error import AkiSyntaxErr


class TestLexer(unittest.TestCase):

    from core import lex, parse

    l = lex.AkiLexer().tokenize
    p = parse.AkiParser().parse

    def __parse(self, text):
        return self._parse(text, True)

    def _parse(self, text, display=False):
        tokens = self.l(text)
        asts = self.p(tokens, text)
        stream = [_.flatten() for _ in asts]
        if display:
            print(stream)
        return stream

    def _e(self, tests):
        for text, result in tests:
            self.assertEqual(self._parse(text), result)

    def test_constant(self):
        self._e(
            (
                (r"32", [["Constant", 32, ["VarType", "i32"]]]),
                (r"32.0", [["Constant", 32, ["VarType", "f32"]]]),
            )
        )

        with self.assertRaises(AkiSyntaxErr):
            self.assertEqual(self._parse(r"32.x"), [])
            self.assertEqual(self._parse(r"x.32"), [])

    def test_expr_names(self):
        self._e(
            (
                (r"x", [["Name", "x", None, None]]),
                (r"_x", [["Name", "_x", None, None]]),
                (
                    r"var x:i32",
                    [["VarList", [["Name", "x", None, ["VarType", "i32"]]]]],
                ),
                (
                    r"var x:i32=1,y=2,z:i32",
                    [
                        [
                            "VarList",
                            [
                                [
                                    "Name",
                                    "x",
                                    ["Constant", 1, ["VarType", "i32"]],
                                    ["VarType", "i32"],
                                ],
                                [
                                    "Name",
                                    "y",
                                    ["Constant", 2, ["VarType", "i32"]],
                                    ["VarType", "None"],
                                ],
                                ["Name", "z", None, ["VarType", "i32"]],
                            ],
                        ]
                    ],
                ),
            )
        )

    def test_binop(self):
        self._e(
            (
                (
                    r"x+1",
                    [
                        [
                            "BinOp",
                            "+",
                            ["Name", "x", None, None],
                            ["Constant", 1, ["VarType", "i32"]],
                        ]
                    ],
                ),
                (
                    r"x+1*5",
                    [
                        [
                            "BinOp",
                            "+",
                            ["Name", "x", None, None],
                            [
                                "BinOp",
                                "*",
                                ["Constant", 1, ["VarType", "i32"]],
                                ["Constant", 5, ["VarType", "i32"]],
                            ],
                        ]
                    ],
                ),
            )
        )

    def test_unop(self):
        self._e(
            (
                (r"-5", [["UnOp", "-", ["Constant", 5, ["VarType", "i32"]]]]),
                (
                    r"-{x*y}",
                    [
                        [
                            "UnOp",
                            "-",
                            [
                                "ExpressionBlock",
                                [
                                    [
                                        "BinOp",
                                        "*",
                                        ["Name", "x", None, None],
                                        ["Name", "y", None, None],
                                    ]
                                ],
                            ],
                        ]
                    ],
                ),
            )
        )

    def test_assignment(self):
        self._e(
            (
                (
                    r"x=5",
                    [
                        [
                            "Assignment",
                            "=",
                            ["Name", "x", None, None],
                            ["Constant", 5, ["VarType", "i32"]],
                        ]
                    ],
                ),
            )
        )

    def test_expr_paren(self):
        self._e(
            (
                (
                    r"(x==1)",
                    [
                        [
                            "BinOpComparison",
                            "==",
                            ["Name", "x", None, None],
                            ["Constant", 1, ["VarType", "i32"]],
                        ]
                    ],
                ),
                (
                    r"(x=1)",
                    [
                        [
                            "Assignment",
                            "=",
                            ["Name", "x", None, None],
                            ["Constant", 1, ["VarType", "i32"]],
                        ]
                    ],
                ),
            )
        )

        with self.assertRaises(AkiSyntaxErr):
            self.assertEqual(self._parse(r"(x=1 x=2)"), [])

    def text_expr_block(self):
        self._e(
            (
                (
                    r"{x=1 x==1}",
                    [
                        [
                            "ExpressionBlock",
                            [
                                [
                                    "Assignment",
                                    "=",
                                    ["Name", "x", None, None],
                                    ["Constant", 1, ["VarType", "i32"]],
                                ],
                                [
                                    "BinOpComparison",
                                    "==",
                                    ["Name", "x", None, None],
                                    ["Constant", 1, ["VarType", "i32"]],
                                ],
                            ],
                        ]
                    ],
                )
            )
        )

    def test_toplevel_def(self):
        self._e(
            (
                (
                    "def main(){0}",
                    [
                        [
                            "Function",
                            ["Prototype", [], ["VarType", "None"]],
                            [["Constant", 0, ["VarType", "i32"]]],
                        ]
                    ],
                ),
            )
        )

    def test_function_def(self):
        self._e(
            (
                (
                    r"def main(x){x+=1 x}",
                    [
                        [
                            "Function",
                            [
                                "Prototype",
                                [["Argument", "x", ["VarType", "None"]]],
                                ["VarType", "None"],
                            ],
                            [
                                [
                                    "Assignment",
                                    "=",
                                    ["Name", "x", None, None],
                                    [
                                        "BinOp",
                                        "+",
                                        ["Name", "x", None, None],
                                        ["Constant", 1, ["VarType", "i32"]],
                                    ],
                                ],
                                ["Name", "x", None, None],
                            ],
                        ]
                    ],
                ),
            )
        )

    def test_loop(self):
        self._e(
            (
                (
                    r"loop (x=0,x<20,x+1){x}",
                    [
                        [
                            "LoopExpr",
                            [
                                [
                                    "Assignment",
                                    "=",
                                    ["Name", "x", None, None],
                                    ["Constant", 0, ["VarType", "i32"]],
                                ],
                                [
                                    "BinOpComparison",
                                    "<",
                                    ["Name", "x", None, None],
                                    ["Constant", 20, ["VarType", "i32"]],
                                ],
                                [
                                    "BinOp",
                                    "+",
                                    ["Name", "x", None, None],
                                    ["Constant", 1, ["VarType", "i32"]],
                                ],
                            ],
                            ["ExpressionBlock", [["Name", "x", None, None]]],
                        ]
                    ],
                ),
                (
                    r"loop (var x=0,x<20,x+1){x}",
                    [
                        [
                            "LoopExpr",
                            [
                                [
                                    "VarList",
                                    [
                                        [
                                            "Name",
                                            "x",
                                            ["Constant", 0, ["VarType", "i32"]],
                                            ["VarType", "None"],
                                        ]
                                    ],
                                ],
                                [
                                    "BinOpComparison",
                                    "<",
                                    ["Name", "x", None, None],
                                    ["Constant", 20, ["VarType", "i32"]],
                                ],
                                [
                                    "BinOp",
                                    "+",
                                    ["Name", "x", None, None],
                                    ["Constant", 1, ["VarType", "i32"]],
                                ],
                            ],
                            ["ExpressionBlock", [["Name", "x", None, None]]],
                        ]
                    ],
                ),
            )
        )

    def test_if_else(self):
        self._e(
            (
                (
                    r"if x>1 y else z",
                    [
                        [
                            "IfExpr",
                            [
                                "BinOpComparison",
                                ">",
                                ["Name", "x", None, None],
                                ["Constant", 1, ["VarType", "i32"]],
                            ],
                            ["Name", "y", None, None],
                            ["Name", "z", None, None],
                        ]
                    ],
                ),
                (
                    r"if (x>1) (y) else (z)",
                    [
                        [
                            "IfExpr",
                            [
                                "BinOpComparison",
                                ">",
                                ["Name", "x", None, None],
                                ["Constant", 1, ["VarType", "i32"]],
                            ],
                            ["Name", "y", None, None],
                            ["Name", "z", None, None],
                        ]
                    ],
                ),
                (
                    r"if {x>1} {y} else {z}",
                    [
                        [
                            "IfExpr",
                            [
                                "ExpressionBlock",
                                [
                                    [
                                        "BinOpComparison",
                                        ">",
                                        ["Name", "x", None, None],
                                        ["Constant", 1, ["VarType", "i32"]],
                                    ]
                                ],
                            ],
                            ["ExpressionBlock", [["Name", "y", None, None]]],
                            ["ExpressionBlock", [["Name", "z", None, None]]],
                        ]
                    ],
                ),
            )
        )

    def test_when(self):
        self._e(
            (
                (
                    r"when x>1 y else z",
                    [
                        [
                            "WhenExpr",
                            [
                                "BinOpComparison",
                                ">",
                                ["Name", "x", None, None],
                                ["Constant", 1, ["VarType", "i32"]],
                            ],
                            ["Name", "y", None, None],
                            ["Name", "z", None, None],
                        ]
                    ],
                ),
                (
                    r"when {x>1} {y} else {z}",
                    [
                        [
                            "WhenExpr",
                            [
                                "ExpressionBlock",
                                [
                                    [
                                        "BinOpComparison",
                                        ">",
                                        ["Name", "x", None, None],
                                        ["Constant", 1, ["VarType", "i32"]],
                                    ]
                                ],
                            ],
                            ["ExpressionBlock", [["Name", "y", None, None]]],
                            ["ExpressionBlock", [["Name", "z", None, None]]],
                        ]
                    ],
                ),
            )
        )

    def test_with(self):
        self._e(
            (
                (
                    r"with var x=1 {x}",
                    [
                        [
                            "WithExpr",
                            [
                                [
                                    "Name",
                                    "x",
                                    ["Constant", 1, ["VarType", "i32"]],
                                    ["VarType", "None"],
                                ]
                            ],
                            ["ExpressionBlock", [["Name", "x", None, None]]],
                        ]
                    ],
                ),
                (
                    r"with var x=1, y=2 {x}",
                    [
                        [
                            "WithExpr",
                            [
                                [
                                    "Name",
                                    "x",
                                    ["Constant", 1, ["VarType", "i32"]],
                                    ["VarType", "None"],
                                ],
                                [
                                    "Name",
                                    "y",
                                    ["Constant", 2, ["VarType", "i32"]],
                                    ["VarType", "None"],
                                ],
                            ],
                            ["ExpressionBlock", [["Name", "x", None, None]]],
                        ]
                    ],
                ),
            )
        )

    def test_break(self):
        self._e(
            ((r"loop {break}", [["LoopExpr", [], ["ExpressionBlock", [["Break"]]]]]),)
        )

    def test_call(self):
        self._e(((r"x(1)", [["Call", [["Constant", 1, ["VarType", "i32"]]], None]]),))

