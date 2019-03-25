if __name__ == "__main__":
    import sys, gc, msvcrt
    init_modules = set(sys.modules.keys())
    while True:
        from core import repl
        from core.error import ReloadException, QuitException
        try:
            repl.Repl().run()
        except ReloadException:
            gc.unfreeze()
            for m in reversed(list(sys.modules.keys())):
                if m not in init_modules:
                    del sys.modules[m]
            gc.collect()
            msvcrt.heapmin()
            continue
        except QuitException:
            break