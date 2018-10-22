def run(**options):
    import sys, gc, msvcrt
    init_modules = set(sys.modules.keys())
    while True:
        from core.repl import Repl
        from core.errors import ReloadException
        try:
            #repl.run(options)
            Repl().run(options)
            break
        except ReloadException:
            del Repl
            #del repl
            del ReloadException
            for m in reversed(list(sys.modules.keys())):
                if m not in init_modules:
                    del sys.modules[m]            
            gc.collect()
            msvcrt.heapmin()
            continue


if __name__ == '__main__':
    run()
