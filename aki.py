def run(**options):
    import sys
    init_modules = set(sys.modules.keys())
    from core import repl
    while True:
        try:
            repl.run(options)
            break
        except repl.ReloadException:
            for m in list(sys.modules.keys()):
                if m not in init_modules:
                    del (sys.modules[m])
            from core import repl
            continue

if __name__ == '__main__':
    run()
