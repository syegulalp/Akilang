# Stage 0: Absolute basics

## Completed

* [x] Lexer
* [x] Parser
* [x] AST nodes
* [x] Function prototype
* [x] Function body
* [x] Return value
* [x] JIT compiler
* [x] Basic types: `i/u32/64, f32/64`
* [x] Math (`+, - , *, /, +=, -=`)
  * [ ] `//` (integer-only division, always returns an `int` of some kind)
* [x] Multi-statement procedures 
* [x] Load from file (primitive)
* [x] Detailed error messages
  * [x] Including lexer/parser error handling
* [x] Function calls
  * [x] Anonymous calls in CLI
* [x] `if/else` (yields expression)
* [x] `when/else` (yields result of test)
* [x] Comparison ops (`==, !=, <, >, <=, >=, and, or`)
  * [x] also bitwise and/or by way of `&` and `|` ops
* [x] Unary ops
  * [x] (`-`) - numerical (bitwise)
  * [x] (`not`) - logical (`i1` result)
* [x] Variable declarations, assignment, retrieval
  * [x] Declaration/init
  * [x] Retrieval
  * [x] Assignment
* [x] Loop constructions
  * [x] Var inside and outside of loops
  * [x] `break` to exit from blocks
  * [ ] Autoincrement/assume infinite loop
* [x] Loaded programs and REPL use different JITs to allow efficient code reuse
* [x] `with` context for variables
* [x] Test suite
  * [x] Lexer
  * [x] Parser
  * [x] Compiler
  * [ ] Compile to standalone binary
* [x] Default function argument values
* [x] Color-coded output in REPL
* [x] Store Aki-native type signatures as LLVM metadata
* [x] Pointers and pointer types, mainly for compatibility with C right now
  * [x] `ref`/`deref` (to create and dereference pointers)
  * [ ] Pointer comparisons
  * [ ] Pointer math (may require its own type)
* [x] Function type (for function pointers)
  * [x] Function pointer type
  * [x] String constants
* [x] Comments
* [x] Extract C-compatible data from Aki structures
* [x] External function references (`extern` keyword)
* [x] `cast`
  * [x] Unsafe `cast`
  * [x] Casting int to pointer and back (`unsafe` only)
* [x] Inline typing for constants
  * [x] `True/False` for `bool` values
  * [x] `0x00` and `0h00` for unsigned and signed values, respectively
  * [x] Inline constant type declarations (e.g., `4096:u_size`)
* [x] `unsafe` context block for certain operations  
* [x] Variable argument functions (for compatibility with C calls)
* [x] String escape characters (e.g., `\x00` for inline hex)
  * [x] Escaped quoting (`'It\'s a quote!'`)
  * [x] Escape slashes (`\\` = \\)
* [x] Array type
  * [x] Support for objects in arrays
  * [x] N-dimensional arrays of scalars
* [x] `uni` for globals
* [x] `case` statement for matching against constant enums (including type enumerators)
* [x] `while` expressions
* [x] `const` for constants
* [x] Decorators by way of the `@` symbol
  * [x] `inline`/`noinline` for functions

## In progress
* [ ] Compile-time computation of constants and values for `uni` assignments
* [ ] Classes and object structures
  * [ ] Object methods and method calls
* [ ] Type declarations (aliases)
* [ ] `print` builtin
* [ ] `meta` keyword for program metadata (compiler directives, etc.)
* [ ] Complete REPL command set (as per earlier incarnation of project)
* [ ] CLI command support
* [ ] Compile to standalone binary, maybe with `lld` instead of the platform linker
* [ ] Type conversions

# Stage 1: Advanced variables and structures
* [ ] Slices
* [ ] Enums
* [ ] Iterables by way of object methods
* [ ] String operations
  * [ ] String slices
* [ ] Call chains

# Stage 2: Advanced error handling

* [ ] Error/option types

# Stage 3: Modules

* [ ] Module imports

# Stage 4: Other stuff

* [ ] Container objects
* [ ] Lists
  * [ ] Prereq for functions that take arbitrary numbers of arguments (since they are just list objects)
* [ ] Dictionaries/hashmaps
  * [ ] Prereq for functions that take named arguments (since they are just dicts with string keys)
* [ ] Sets
* [ ] Auto-conversion rules for scalars?

# Stage 5: Beyond The Impossible (for me right now, anyway)

* [ ] Garbage collection
* [ ] Use existing C headers as-is
* [ ] Threading, actors, coroutines, etc.