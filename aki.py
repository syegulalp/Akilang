from importlib import reload

import llvmlite_custom

import repl

def run(**options):
    while(True):
        try:
            repl.run(options)
            break
        except repl.ReloadException:
            reload(repl)
            continue

if __name__ == '__main__':
    run()
