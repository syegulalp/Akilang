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
  * [ ] `//` (integer-only division)
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
* [x] Loaded programs and REPL use different JITs to allow efficient code reuse

## In progress

* [ ] `with` context for variables
* [ ] `case` statement for matching against enums
* [ ] Comments
* [ ] Inline typing for constants
* [ ] Function type
* [ ] Test suite
  * [x] Lexer
  * [ ] Parser
  * [ ] Compiler
* [ ] Complete CLI
* [ ] Compile to standalone binary, maybe with `lld` instead of the platform linker.

# Stage 1: Advanced variables and structures

* [ ] Strings
* [ ] N-dimensional arrays of scalars
* [ ] Array and string slices
* [ ] Classes and basic object structures
* [ ] Auto-conversion rules for scalars
* [ ] Call chains

# Stage 2: Advanced error handling

# Stage 3: Modules