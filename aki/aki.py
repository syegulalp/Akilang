if __name__ == "__main__":    
    #import cProfile, pstats, io
    #pr = cProfile.Profile()
    #pr.enable()
    import sys
    init_modules = set(sys.modules.keys())
    while True:
        from core import repl
        from core.error import ReloadException, QuitException
        try:
            repl.Repl().run(True)
        except ReloadException:
            for m in reversed(list(sys.modules.keys())):
                if m not in init_modules:
                    del sys.modules[m]
            continue
        except QuitException:
            #pr.disable()
            #s = io.StringIO()
            #sortby = pstats.SortKey.CUMULATIVE
            #ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
            #ps.print_stats()            
            #with open ('stats.txt','w') as file:
                #file.write(s.getvalue())
            break