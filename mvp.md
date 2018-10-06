# Features for a Minimum Viable Aki

(in, very roughly, order of importance/implementation)

- [x] REPL.
- [x] Scalar types: `int(8, 32, 64), float, boolean`
    - [x] Signed and unsigned scalar types.
    - [x] `cast` and `convert` operations for primitive numerical types.
    - [x] Type checking for basic assignment operations.
    - [x] Type checking for math. (I think we did this)
- [ ] *N*-dimensional arrays of scalar types.
    - [x] Array references.
    - [ ] Array slices (return new arrays)
- [x] Strings.
    - [ ] String slices.
    - [ ] String operations.
        - [ ] Comparisons.
        - [x] `len()` of strings.
        - [x] `str()` for creating strings from other types.
- [x] Constants.
    - [x] Constant definitions.
    - [x] Constant folding/lowering.
- [ ] Support for basic logic and keywords:
    - [x] `def`
    - [x] `do`
    - [x] `if / then / else`
    - [x] `when / then / else`
    - [x] `while`
    - [x] `var` (unscoped variable declaration)
    - [ ] `with` (context mgr)
        - [x] `with var` (scoped variable declaration)
    - [x] `return` (including early return)
    - [x] `loop`
    - [x] `break`
    - [x] `match` (for scalar types only)
- [x] Global and local variables (`var`, `uni`).
- [ ] Object type.
    - [x] Object definitions (`class`).
    - [x] Bound functions / "dunder" methods for objects.
- [ ] Pointer syntax for interfacing with C.
    - [x] Get pointer
    - [x] Dereference pointer
    - [x] Get raw data from complex object (right now only strings)
    - [x] Function pointers.
- [ ] Memory management
    - [x] Manual heap memory management.
    - [ ] Heap-based memory management for things that need it (e.g., `class` objects returned from a function).
    - [ ] Automatic heap memory management (object destructor called when it goes out of scope)    
- [ ] Type definitions / aliases, apart from object types. (`alias`?)
- [ ] Variable arguments.
    - [ ] Variable length arguments for functions.
    - [x] Optional arguments.
    - [x] Default arguments.
- [x] Compiling to standalone binaries.
    - [ ] Command-line parameters for binaries.
- [x] Print statement that supports scalar types, and strings too.
    - [ ] Variable argument printing.
    - [X] F-string style syntaxing.
- [ ] Overflow detection for math, and minimal error handling.
- [X] Decorator syntax.
- [ ] Meta/pragma syntax.
- [ ] Integers of arbitrary length, for bignum support.
- [ ] Documentation.

# Next phase
- [ ] Ports to other platforms, mainly Linux.
- [ ] Properly refactored deployment and improved code quality.
    - [ ] Use a parser generator so we can also generate a grammar for the language (e.g., for use by syntax highlighters)
- [ ] Robust error handling inside the language (object-based exceptions).
- [ ] More robust memory management details, including optional garbage collected objects.
- [ ] More object types.
- [ ] File I/O.
- [ ] Proof-of-concept standard library with math functions.
- [ ] Proof-of-concept module system.
- [ ] Proof-of-concept module-level metadata.
- [ ] Full test suite support.
- [ ] Networking, even if it's just an interface to sockets on the platform.
- [ ] Debugging features.

# Someday? Maybe?

- [ ] Self-hosting.