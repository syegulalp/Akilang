# **Aki**:  a compiler for a simple language, built with Python 3.6+ and the [LLVM framework](https://www.llvm.org) by way of the [llvmlite](http://llvmlite.pydata.org/en/latest/) library

> ⚠ This project is currently very unstable and should not be used in production. However, you should always be able to pull from `master`, run the demos, and pass the test suite. (The test suite compiles the demos internally as well.)

This project is an attempt to create a compiler, language server, and REPL in Python for a simple language that's compiled to native machine code.

Eventually, this might become something useful for real work. Right now, it's strictly proof-of-concept -- a fun toy for me to hack on and to learn about compiler theory and programming language construction in the process.

* [This document](language.md) is a work-in-progress tour of the language's syntax.
* [This document](whats-next.md) gives you an idea of what's being worked on right now and in the near future.
* [The official blog](https://aki.genjipress.com) tracks development and discussion of the project. (Not updated often)
* You can see a demo movie (now outdated) of the language in action [here.](https://www.youtube.com/watch?v=9vZ4oFCFOl8)

**If you're a fan of Python, LLVM, compilers, or any combination of the above, [learn how to contribute.](CONTRIBUTING.md)**

# Features, goals, and ideals

The language's syntax and goals are in heavy flux, but this is the basic idea I want to aim for:

* Compile to compact machine-native code with a minimal runtime and as few external dependencies as possible.
* Use LLVM as our code generation system, so we can theoretically compile to any target LLVM supports, like WebAssembly.
* Strong typing, eventually to be made dynamic by way of an object system a la Python.
* Keep the core of the language small, but provide useful native constructs a la Python (Unicode strings, lists, dictionaries, tuples, sets, etc.).
* Your choice of memory management methods as need dictates. Use garbage collected memory management when you need to throw together a quick script; use static memory management (by way of syntactical constructions) when you want speed and performance.
* A batteries-included standard library, yet again like Python.
* Good tooling for package and project management, including out-of-the-box code formatting tools, akin to Rust/Go/C#.
* Integrated support for C libraries; the ability to import a C header file for a (compiled) library and use it as-is.
* While we're dreaming: Make the language self-hosting.

Even if any of these features are only implemented in miniature, the idea would be to polish the implementations as completely as possible, so they could set the best possible example. For instance, if the standard library only had a proof-of-concept number of modules, the *way* they worked would be refined so that the practices around them could support a larger standard library.

By deliberately keeping the scope of the implementation at PoC level (or, rather, by accepting such a scope as a by-product of the fact that this is a hobby project for now), it ought to be easier to keep a good grasp on the basics, and to avoid conceptual problems that could bite us later. It also makes it easier to tear down and rebuild in the event we find we've written ourselves into a conceptual corner.

Another likely goal would be to make this a language that encourages quick interactive development by way of its workflow. For instance, invoking the compiler with a certain set of command-line switches would fire up an editor for a new or existing project, and preconfigure the REPL to reload-and-run that project whenever you input the `.rlr` command.

Finally, I'm not looking at this as a "replacement" for any existing language, just something that takes good cues from the galaxy of other languages out there.

# "Aki's Way"

Some guidelines about what we want Aki to be, by way of aphorisms (also in flux). These are not dogma, just directions to lean in:

* Fast is good, easy is better, useful is best -- and sometimes also fastest, too.
* Just enough is more.
* You should be able to lift the hood if you *need* to, but the vast majority of the time you shouldn't *have* to.
* Solve the right problems at the right level, and in a way that helps as many others as possible.
* Don't include *now* what we don't need *now*.
* Eschew ambiguity, but embrace practical brevity.

# Code examples

> Note that these do not work yet. This message will go away when they do.

## Hello, world!

```
def main() {
    
    print('Hello world!')
    # you can use "" or '' to delineate strings as long as they match

    print("こんにちは世界!")
    # Unicode is allowed

    print("Goodbye
world!") # so are multi-line strings, as linebreaks are arbitrary

    0

    # every statement is an expression,
    # and the last statement of a function is an implicit return,
    # but we do have a `return` keyword for early returns,
    # so the last line could also be: `return 0`
}
```

(Eventually, for quick-and-dirty scripting, we'll ditch the need for a `main()` function.)

## Fibonacci sequence

```
def main() {
    var a = 0:u64, b = 1:u64, c = 0:u64
    # :u64 = unsigned 64-bit integer
    loop (x = 0, x < 50) {
        # by default loops increment by one
        print (a)
        c = a + b
        a = b
        b = c
    }
    return 0
}
```

# Quickstart

You'll need Python 3.6 and Windows 10 64-bit.

1. Clone or download the repo.
2. `pip install -r requirements.txt` to ensure you have all the requirements.
3. Run `python aki.py` to start the REPL.
4. Enter `.l.` to load the Conway's Life demo from the `examples` directory.
5. Enter `.r` to run the demo.
6. Hit `q` to exit Conway's Life. Enter `.` to see all commands.
<!-- 7. If you have the Microsoft Visual Studio tools installed, you can enter `.l.` to load the Conway's Life demo, then enter `.cp` to compile it to a standalone binary in the `\output` subdirectory. (Make sure `nt_compiler_path` in `config.ini` points to the correct location for `vcvarsall.bat`. This limitation will be removed in the future.) -->

There's also going to be a standalone binary version of the compiler, most likely by way of `pyinstaller`.


# Limitations

(Apart from the language itself being a minimal affair, that is.)

* Currently only Windows 10 64-bit is supported. We'd like to add support for other systems in time, though.
* We have no plans to support any text encoding other than UTF-8, plus whatever encodings are used in the kernel of a given target platform (e.g., UTF-16 for Windows).

# Derivation and licensing

This project is based (very loosely) on the 
[Pykaleidoscope project](https://github.com/frederickjeanguerin/pykaleidoscope) by [Frédéric Guérin](https://github.com/frederickjeanguerin), 
derived in turn from the [Pykaleidoscope project](https://github.com/eliben/pykaleidoscope) by [Eli Bendersky](https://github.com/eliben). (An earlier version of this project used their code directly; this version is a complete rewrite from scratch.)

The original Pykaleidoscope project was made available under the [Unlicense](https://github.com/eliben/pykaleidoscope/blob/master/LICENSE). This version is distributed under the [MIT license](LICENSE).

Licensing for included and to-be-included modules:

* [llvmlite](http://llvmlite.pydata.org/en/latest/): [BSD 2-Clause "Simplified" License](https://github.com/numba/llvmlite/blob/master/LICENSE)
* [termcolor](https://pypi.org/project/termcolor/): MIT License
* [colorama](https://pypi.org/project/colorama/): [BSD License](https://github.com/tartley/colorama/blob/master/LICENSE.txt)
* [lark-parser](https://github.com/lark-parser/lark/): [MIT license](https://github.com/lark-parser/lark/blob/master/LICENSE)
