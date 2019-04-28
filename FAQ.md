# What is Akilang? What is Aki?

Aki, or Akilang, is a simple programming language. The first compiler for that language is written in Python, and using LLVM by way of the `llvmlite` library.

# What's your goal for the language?

Aki isn't meant to "replace" any existing languages or be a "challenge" to them. It's mainly a learning experience for the author and whoever else wants to help implement it. If in time it becomes something truly useful, even a challenge to existing languages, great. But the main goal is to learn compiler theory and programming language design by doing.

# Is Aki interpreted?

Aki compiles to native machine code. By default it compiles to the machine the compiler is running on, but in time we'll support emitting code for other targets.

# Can I run Aki programs on (insert platform here)?

In theory Aki programs can run anywhere LLVM has a target. Aki emits LLVM IR and bitcode, which can be compiled more or less independently of Aki itself. However, the only implementation of the compiler right now is for Microsoft Windows 10, 64-bit edition, although since it's written in Python it can also in theory be ported pretty easily to other platforms. (Windows is the chief developer's main platform.)

# What kinds of programs can I write with Aki?

At first, Aki will not be very useful. I don't expect to be able to support programs that do more than perform basic math, and print to and read from the console. In time, though, I hope to make its core as useful as, say, Python without its standard library.

# Will Aki have garbage collected memory management (e.g., Python, Go) or scope/lifetime-based memory management (e.g., Rust)?

I'm hoping to allow both where possible. Right now it doesn't have any functional memory management, as it is still in the very early stages.

# Can I contribute a feature or a bugfix?

Absolutely. See [CONTRIBUTING](CONTRIBUTING.md) for more details.