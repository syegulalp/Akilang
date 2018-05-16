# Features for a Minimum Viable Aki

- [x] REPL.
- [x] Scalar types: `int(8, 32, 64), float, boolean`
    - [x] `cast` and `convert` operations for primitive numerical types.
    - [x] Type checking for basic assignment operations.
    - [ ] Type checking for math. (I think we did this)
- [ ] *N*-dimensional arrays of scalar types.
    - [x] Array references.
    - [ ] Array slices (return new arrays)
- [x] Strings.
    - [ ] String slices.
    - [ ] String operations.
        - [ ] Comparisons.
        - [ ] `len()` of strings.
        - [ ] `str()` for creating strings from other types.
- [ ] Constants
    - [X] Constant definitions.
    - [ ] Constant folding/lowering.
- [ ] Support for basic logic and keywords:
    - [x] `def`
    - [x] `do`
    - [x] `if / then / else`
    - [ ] `when / then / else`
    - [ ] `while`
    - [x] `var` (scoped variable declaration)
    - [x] `let` (unscoped)
    - [x] `return` (including early return)
    - [x] `loop`
    - [x] `break`
    - [x] `match` (for scalar types only)
- [x] Global and local variables.    
- [ ] Variable length arguments for functions.
- [ ] Default arguments.
- [x] Compiling to standalone binaries.
    - [ ] Command-line parameters for binaries.
- [x] Print statement that supports scalar types, and strings too.
    - [ ] Variable argument printing.
    - [ ] F-string style syntaxing.
- [ ] Pointer syntax for interfacing with C.
    - [x] Get pointer
    - [x] Dereference pointer
    - [x] Get raw data from complex object (right now only strings)
    - [ ] Function pointers.
- [ ] Object type.
    - [x] Object definitions.
    - [ ] Bound functions / "dunder" methods for objects.
- [ ] Overflow detection for math, and minimal error handling.
- [ ] Integers of abritrary length, for bignum support.

# Next phase
- [ ] Ports to other platforms, mainly Linux.
- [ ] Properly refactored deployment and improved code quality.
    - [ ] Use a parser generator so we can also generate a grammar for the language (e.g., for use by syntax highlighters)
- [ ] Robust error handling inside the language (object-based exceptions).
- [ ] More robust memory management details, including optional garbage collected objects.
- [ ] Decorator syntax.
- [ ] Meta/pragma syntax.
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