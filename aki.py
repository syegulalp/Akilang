def run(**options):
    from aki import repl    
    from importlib import reload
    while(True):
        try:
            repl.run(options)
            break
        except repl.ReloadException:
            reload(repl)
            continue

if __name__ == '__main__':
    run()
