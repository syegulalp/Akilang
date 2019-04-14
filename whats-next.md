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
* [x] Function type (for function pointers)
  * [x] Function pointer type
  * [x] String constants

## In progress

* [ ] Inline typing for constants
  * [x] `True/False` for `bool` values
  * [x] `0x00` and `0h00` for unsigned and signed values, respectively
  * [ ] Cast from constant, e.g. `i32(100)` or `f64(1.0)`
* [ ] External function references (`extern` context block with optional library identifier)
* [ ] `case` statement for matching against enums
* [ ] `while` constructions
* [ ] Comments
* [ ] `uni` for globals
* [ ] `const` for constants
* [ ] Complete REPL command set (as per earlier incarnation of project)
* [ ] CLI command support
* [ ] Compile to standalone binary, maybe with `lld` instead of the platform linker
* [ ] Positional and named/optional arguments
* [ ] Type conversions
* [ ] Function name mangling

# Stage 1: Advanced variables and structures

* [ ] N-dimensional arrays of scalars
* [ ] Type declarations
* [ ] Enums
* [ ] Classes and object structures
* [ ] Object methods and method calls
* [ ] Iterables by way of object methods
* [ ] Array slices
* [ ] Strings
* [ ] String slices
* [ ] Call chains

# Stage 2: Advanced error handling

* [ ] Error/option types

# Stage 3: Modules

* [ ] Module imports

# Stage 4: Other stuff

* [ ] Container objects
* [ ] Lists
* [ ] Dictionaries/hashmaps
* [ ] Sets
* [ ] Auto-conversion rules for scalars?

# Stage 5: Beyond The Impossible (for me right now, anyway)

* [ ] Garbage collection
* [ ] Use existing C headers as-is
* [ ] Threading, actors, coroutines, etc.