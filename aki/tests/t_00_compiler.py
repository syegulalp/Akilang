# Test compiler by having it compile all example apps.
# This is a good way to fail fast if we break something major,
# especially since our examples all need to compile.

# This should also include module load and name cross-linking tests,
# e.g. the `g1()+g1()` test

import unittest


class TestLexer(unittest.TestCase):
    from core.repl import Repl
    #from core.akitypes import AkiTypeMgr

    #mgr = AkiTypeMgr()
    #types = mgr.types
    #r = Repl(typemgr=mgr)
    r = Repl()
    i = r.interactive

    def e(self, test, result):
        _ = [_ for _ in self.i(test, False)][0]
        self.assertEqual(_, result)

    def test_load_1(self):
        self.r.load_file("test_1", ignore_cache=True)
        self.e("g1()+g1()", 38)

    def test_load_2(self):
        self.r.load_file("test_2", ignore_cache=True)
        self.e('print("Hello world!")', 13)

    def test_load_3(self):
        # Right now we're just trying to see if the Life file compiles
        self.r.load_file("l", ignore_cache=True)

