# Test compiler by having it compile all example apps.
# This is a good way to fail fast if we break something major,
# especially since our examples all need to compile.

# This should also include module load and name cross-linking tests,
# e.g. the `g1()+g1()` test

import unittest
from core.error import AkiTypeErr, AkiSyntaxErr, AkiBaseErr
from core.akitypes import AkiTypeMgr


class TestLexer(unittest.TestCase):
    from core.repl import Repl

    mgr = AkiTypeMgr()
    types = mgr.types
    r = Repl(typemgr=mgr)
    i = r.interactive

    def _e(self, tests):
        for text, result in tests:
            for _ in self.i(text, False):
                pass
            self.assertEqual(_, result)

    def _ex(self, err_type, tests):
        with self.assertRaises(err_type):
            for text, result in tests:
                for _ in self.i(text, False):
                    pass

    def test_module_load(self):
        self.r.load_file("1")
        self._e((("g1()+g1()", 38),))
        self.r.load_file("2")
        self._e((('print("Hello world!")', 12),))

