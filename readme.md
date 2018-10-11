**Aki** is a compiler for a simple language, built with Python 3.6+ and the [LLVM framework](https://www.llvm.org) by way of the [llvmlite](http://llvmlite.pydata.org/en/latest/) library.

Eventually, this might become something useful for production. Right now, it's strictly proof-of-concept -- a fun toy for me to hack on and to learn about compiler theory and programming language construction in the process.

> ⚠ This project is currently very unstable and may break between updates.

[This document](whats-next.md) gives you an idea of what's being worked on right now and in the near future.

[This document](language.md) is a work-in-progress tour of the language's syntax.

[This document](memory.md) discusses Aki's aims in terms of memory management.

You can see a short demo movie of the language in action [here.](https://www.youtube.com/watch?v=9vZ4oFCFOl8)

# Goals and ideals

The language's syntax and goals are in heavy flux, but this is the basic idea I want to aim for:

* Compile to compact machine-native code with no external runtime and as few external dependencies as possible.
* Strong typing, eventually to be made dynamic by way of an object system a la Python.
* Keep the core of the language small, but provide useful native constructs a la Python (Unicode strings, lists, dictionaries, tuples, sets, etc.).
* A batteries-included standard library, yet again like Python.
* Good tooling for package and project management, including out-of-the-box code formatting tools, akin to Rust/Go/C#.
* While we're dreaming: Make the language self-hosting.

(A more detailed features-in-progress list is [here](mvp.md).)

Even if any of these features are only implemented in miniature, the idea would be to polish the implementations as completely as possible, so they could set the best possible example. For instance, if the standard library only had a proof-of-concept number of modules, the *way* they worked would be refined so that the practices around them could support a larger standard library.

By deliberately keeping the scope of the implementation at PoC level (or, rather, by accepting such a scope as a by-product of the fact that this is a hobby project for now), it ought to be easier to keep a good grasp on the basics, and to avoid conceptual problems that could bite us later.

Another likely goal would be to make this a language that encourages quick interactive development by way of its workflow. For instance, invoking the compiler with a certain set of command-line switches would fire up an editor for a new or existing project, and preconfigure the REPL to reload-and-run that project whenever you input the `.rlr` command.

Finally, I'm not looking at this as a "replacement" for any existing language, just something that takes good cues from the galaxy of other languages out there.

# "Aki's Way"

Some guidelines about what we want Aki to be, by way of aphorisms (also in flux). These are not dogma, just directions to lean in:

* Fast is good, easy is better, useful is best -- and sometimes also fastest, too.
* Just enough is more.
* You should be able to lift the hood if you *need* to, but the vast majority of the time you shouldn't *have* to.
* Solve the right problems at the right level, and in a way that helps as many others as possible.
* Don't include *now* what we don't need *now*.
* Eschew ambiguity. (The best grammars in life are context-free.)

# Code examples

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
    var a = 0U, b = 1U, c = 0U
    # U = unsigned 64-bit integer
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
2. Run `python aki.py` to start the REPL.
3. Enter `.l.` to load the Conway's Life demo from the `src` directory.
4. Enter `.r` to run the demo.
5. Hit `q` to exit Conway's Life. Enter `.` to see all commands.

There's also going to be a standalone binary version of the compiler, most likely by way of `pyinstaller`.

# Examples

A few built-in code examples are available and can be run from the compiler's REPL:

* [Your basic Fibonacci sequence](src/fib.aki)
* [FizzBuzz](src/fb.aki) (after all, why not?)
* [Conway's Game Of Life](src/l.aki)
* [Robots](src/robots.aki) (incomplete)
* [A rudimentary invocation of a message box on Win32](src/msg.aki)

The idea would be to provide a slew of fun examples that could be run out of the box, eventually including demos that use GUIs.

# Limitations

... Yes, we have them. To wit:

* The only development platform supported right now is Windows 10 64-bit. In theory it should be easy to port to Linux, and I've already made provisions for things like the standard library to exist in incarnations for each platform.
* **Very** messy, α-quality code. Compiler crashes *a lot*; no guarantees that generated programs won't leak memory like crazy, tons of behavioral bugs in the REPL, etc. The included demos described above should work, though.
* Compiled programs depend almost entirely on LLVM's native optimizations for performance. For instance, there's no attempt yet to use SIMD or other vectorization instructions.
* All memory is stack-allocated right now. Heap allocation is in progress but is still very primitive.
* No higher-level error handling mechanisms -- e.g., integer overflows are not trapped in any way.
* No way to obtain command-line parameters for executables.
* [Very minimal language docs.](language.md)
* No file or network I/O.
* No way to create applications that span more than one file or module.
* Processing user input is still highly primitive -- e.g., no way yet to manipulate/slice strings.
* Builds console applications only. No way yet to build windowed-only apps.

There's tons more limitations not enumerated here, but in time I will open them as formal GitHub issues and try to address them.

In sum, don't even *think* about using this for production; if you do, you're either a high roller or you're trying to find out if someone up there likes you.

# Contributing

Pull requests are welcome. See the [Code of Conduct](code-of-conduct.md) for rules about how to interact with and participate in this project.

# Derivation and licensing

This project is based on the 
[Pykaleidoscope project](https://github.com/frederickjeanguerin/pykaleidoscope) by [Frédéric Guérin](https://github.com/frederickjeanguerin), 
derived in turn from the [Pykaleidoscope project](https://github.com/eliben/pykaleidoscope) by [Eli Bendersky](https://github.com/eliben).

The original project was made available under the [Unlicense](https://github.com/eliben/pykaleidoscope/blob/master/LICENSE). This version is distributed under the [MIT license](LICENSE.TXT).

Licensing for subprojects:

* [llvmlite](http://llvmlite.pydata.org/en/latest/): [BSD 2-Clause "Simplified" License](https://github.com/numba/llvmlite/blob/master/LICENSE)
* [termcolor](https://pypi.org/project/termcolor/): MIT License
* [colorama](https://pypi.org/project/colorama/): [BSD License](https://github.com/tartley/colorama/blob/master/LICENSE.txt)

