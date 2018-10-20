def run(**options):
    import sys
    init_modules = set(sys.modules.keys())
    while True:
        from core import repl
        from core.errors import ReloadException
        try:
            repl.run(options)
            break
        except ReloadException:
            del repl
            del ReloadException
            for m in reversed(list(sys.modules.keys())):
                if m not in init_modules:
                    del sys.modules[m]
            continue


if __name__ == '__main__':
    run()
