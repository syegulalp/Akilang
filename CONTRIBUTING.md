# Contributing

Pull requests are welcome.

We most need help with the following:

* Porting to Linux and Mac OS. The project has been constructed so that any dependencies on Windows and its runtime have a level of abstraction between them to make this possible.
* Exporting to and running WebAssembly or other LLVM targets.
* Additions to core functionality and standard library:
  * String handling.
  * Memory management / garbage collection.

# Code Standards

* We use `black` as the standard code formatter.
* We use `mypy` as the linter. (Note that not all the code currently conforms to `mypy` standards; we use it as a guide, not dogma.)

# Code Of Conduct

See the [Code of Conduct](code-of-conduct.md) for rules about how to interact with and participate in this project.
