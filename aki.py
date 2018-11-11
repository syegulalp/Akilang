def run(**options):
    import sys, gc, msvcrt
    init_modules = set(sys.modules.keys())
    while True:
        from core.repl import Repl
        from core.errors import ReloadException
        try:
            Repl().run(options)
            break
        except ReloadException:
            try:
                gc.unfreeze()
            except:
                pass
            del Repl
            del ReloadException
            for m in reversed(list(sys.modules.keys())):
                if m not in init_modules:
                    del sys.modules[m]
            gc.collect()
            msvcrt.heapmin()
            continue


if __name__ == '__main__':
    run()
