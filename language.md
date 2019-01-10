# Aki language basics

This is a document of Aki syntax and usage.

> ⚠ This document is incomplete and is being revised continuously.

- [Aki language basics](#aki-language-basics)
- [Introduction](#introduction)
  - [Expressions](#expressions)
  - [Functions and function calls](#functions-and-function-calls)
    - [Bare function prototypes (a/k/a forward definitions)](#bare-function-prototypes-aka-forward-definitions)
  - [Variables and variable typing](#variables-and-variable-typing)
- [Symbols](#symbols)
  - [Operators](#operators)
    - [`=` Assignment](#-assignment)
    - [`==` Equality test](#-equality-test)
    - [`!=` Negative equality test](#-negative-equality-test)
    - [`>`/`>=` Greater than / or equal to test](#-greater-than--or-equal-to-test)
    - [`<`/`<=` Less than / or equal to test](#-less-than--or-equal-to-test)
    - [`+` Addition operator](#-addition-operator)
    - [`-` Subtraction operator](#--subtraction-operator)
    - [`*` Multiplication operator](#-multiplication-operator)
    - [`/` Division operator](#-division-operator)
    - [`and`/`or`/`xor`/`not` operators](#andorxornot-operators)
  - [Parentheses `()`](#parentheses-)
  - [Curly braces `{}`](#curly-braces-)
  - [Hash symbol `#`](#hash-symbol-)
  - [Decorator symbol `@`](#decorator-symbol-)
- [Top-level keywords](#top-level-keywords)
  - [`binary`](#binary)
  - [`const`](#const)
  - [`class`](#class)
  - [`def`](#def)
  - [`extern`](#extern)
  - [`pragma`](#pragma)
    - [`loop_vectorize`](#loop_vectorize)
    - [`opt_level`](#opt_level)
    - [`size_level`](#size_level)
    - [`slp_vectorize`](#slp_vectorize)
    - [`unroll_loops`](#unroll_loops)
  - [`unary`](#unary)
  - [`uni`](#uni)
- [Keywords](#keywords)
  - [`break`](#break)
  - [`default`](#default)
  - [`if` / `then` / `elif` / `else`](#if--then--elif--else)
  - [`loop`](#loop)
  - [`match`](#match)
  - [`not`](#not)
  - [`return`](#return)
  - [`unsafe`](#unsafe)
  - [`var`](#var)
  - [`while`](#while)
  - [`with`](#with)
  - [`when`](#when)
- [Decorators](#decorators)
  - [`@inline`](#inline)
  - [`@noinline`](#noinline)
  - [`@nomod`](#nomod)
  - [`@unsafe_req`](#unsafe_req)
  - [`@varfunc`](#varfunc)
- [Builtin functions](#builtin-functions)
  - [`box` / `unbox`](#box--unbox)
  - [`c_addr`](#c_addr)
  - [`c_alloc` / `c_free`](#c_alloc--c_free)
  - [`c_data`](#c_data)
  - [`c_gep`](#c_gep)
  - [`c_ref` / `c_deref`](#c_ref--c_deref)
  - [`c_size`](#c_size)
  - [`c_obj_alloc` / `c_obj_free`](#c_obj_alloc--c_obj_free)
  - [`c_obj_ref` / `c_obj_deref`](#c_obj_ref--c_obj_deref)
  - [`c_ptr_int`](#c_ptr_int)
  - [`c_ptr_math`](#c_ptr_math)
  - [`c_ptr_mod`](#c_ptr_mod)
  - [`cast` / `convert`](#cast--convert)
  - [`objtype`](#objtype)
  - [`ord`](#ord)
  - [`type`](#type)
- [Methods](#methods)
  - [`len`](#len)
- [Library functions](#library-functions)
  - [`inkey`](#inkey)
  - [`print`](#print)
- [Types:](#types)
  - [`bool (u1)`](#bool-u1)
  - [`byte (u8)`](#byte-u8)
  - [`i8/16/32/64`](#i8163264)
  - [`u8/16/32/64`](#u8163264)
  - [`f32/64`](#f3264)
  - [`array`](#array)
  - [`obj`](#obj)
  - [`str`](#str)
  - [`ptr`](#ptr)

# Introduction

## Expressions

Expressions are the basic unit of computation in Aki. Each expression returns a value of a specific type. Every statement is itself an expression:

```
5
```

is an expression that returns the value `5`. (The type of this value is the default type for numerical values in Aki, which is a signed 32-bit integer.)

```
print (if x==1 then 'Yes' else 'No')
```

Here, the argument to `print` is an expression that returns one of two compile-time strings depending on the variable `x`. (`print` itself is a wrapper for `printf` and so returns the number of bytes printed.)

The divisions between expressions are normally deduced automatically by the compiler, due to Aki having a context-free grammar. You can also use parentheses to explicitly set expressions apart:

```
(x+y)/(a+b)
```

The whole of the above is also considered a single expression.

Function bodies are considered expressions:

```
def myfunc() 5
```

This defines a function, `myfunc`, which takes no arguments, and returns `5` when invoked by `myfunc()` elsewhere in the code.

To group together one or more expressions procedurally, for instance as a clause in an expression or in the body of a function, use curly braces in a *block*:

```
def main(){
    print ("Hello!")
    var x=invoke()
    x=x+1
    x
}
```

With any expression block, the last expression is the one returned from the block. To that end, the `x` as the last line of the function body here works as an *implicit return.* You could also say:

```
def main(){
    print ("Hello!")
    var x=invoke()
    x=x+1
    return x
}
```

For the most part, Aki does not care about where you place linebreaks, and is insensitive to indentation. Expressions and strings can span multiple lines.

However, comments (anything starting with a `#`) end with a linebreak.

## Functions and function calls

Use the `def` top-level keyword to define a function:

```
def f1(x:i32):i32 x
```

Function definitions need to have:

* a name that does not shadow any existing name or keyword (except for functions with varying type signatures, where the same name can be reused, or where a bare prototype is redefined with the same type signature and an actual function body)
* zero or more explicitly-typed arguments
* a return type
* and a function body.

In the above example:
* the name is `f1`
* the single argument is `x`, with an explicit type of `i32`
* the return type is `i32`
* and the body is simply the expression `x`.

A more complex function body example:

```
def f1(x:i32):i32 {
    x = (if x>0 then 1 else -1)
    x * 5
}
```

Multiple versions of a function can be written to accept different type signatures:

```
def f1(x:i32):i32 {
    x = (if x>0 then 1 else -1)
    x * 5
}

def f1(x:i8):i32 {
    f1(cast(x,i32))
}
```

The second `f1` takes an `i8`, `cast`s it to `i32`, and supplies that to the `f1` that takes an `i32`.

Functions can also take optional arguments with defaults:

```
def f1(x:i32, y:i32=1) x+y
```

Invoking this with `f1(0,32)` would return `32`. With `f1(1)`, you'd get `2`.

Note that optional arguments must always follow mandatory arguments.

### Bare function prototypes (a/k/a forward definitions)

A "bare" function prototype, also known as a forward definition, can be defined by simply having a function with a blank body:

```
def my_function_to_be_defined_in_full_later(): pass

[...]

def x(): {
    my_function_to_be_defined_in_full_later()
}

[...]

def my_function_to_be_defined_in_full_later(): {
    [actual function with full body]
}
```

## Variables and variable typing

There is no shadowing of variable names permitted anywhere. You cannot have the same name for a variable in both the universal and current scope.

Scalar types -- integers, floats, booleans -- are passed by value. All other objects (classes, strings, etc.) are automatically passed by reference, by way of a pointer to the object.

# Symbols

## Operators

The following operator symbols are predefined:

### `=` Assignment

`var x:i32=5`

### `==` Equality test

`if x==5 then print("OK") else print ("No)`

### `!=` Negative equality test

`if x!=5 then print("No") else print ("OK")`

### `>`/`>=` Greater than / or equal to test

`if x>=5 then print ("OK") else print ("No")`

### `<`/`<=` Less than / or equal to test

`if x<=5 then print ("OK") else print ("No")`

### `+` Addition operator

`x=x+1`

### `-` Subtraction operator

`x=x-1`

### `*` Multiplication operator

`x=x*5`

### `/` Division operator

`x=x/2`

### `and`/`or`/`xor`/`not` operators

Logical `and`, `or`, `xor`, and `not`.

## Parentheses `()`

Parentheses are used to set aside clauses in expressions, and to identify the arguments for a function.

## Curly braces `{}`

Curly braces are used to set aside expression blocks.

## Hash symbol `#`

The hash symbol is a comment to the end of a line. (This is one of the few cases where linebreaks are honored as syntax.)

```
def main(){
    # This is a comment.
    do_something() # Comment after statement.
}
```

There is no block comment syntax. However, an inline string can span multiple lines, and is discarded at compile time if it isn't assigned to anything. This can be used for multiline comments.

```
def main(){
    'This is a multiline
    string that could be a comment.'
    do_something()
}
```

## Decorator symbol `@`

The `@` symbol is used to indicate a [decorator](#decorators).


# Top-level keywords


"Top-level" keywords can only appear as the first level of keywords encountered by the compiler in a module. E.g., you can have a `def` as a top-level keyword, but you cannot enclose another `def` or a `const` block inside a `def`. (At least, not yet!)


## `binary`

The `binary` keyword is used in a function signature to define a binary operator, with an optional precedence.

From the standard library:

```
def binary mod 10 (lhs, rhs)
    lhs - rhs * (lhs/rhs)
```

This defines a binary named `mod` (equivalent to the `%` operator in Python).

The `10` is the operator precedence, with lower numbers having higher precedence.

## `const`

A `const` block is used to define compile-time constants for a module. 


```
const {
    x=10,
    y=20
}

def main(){
    print (x+5) # x becomes 10 at compile time, so this is always 15
}
```

There can be more than one `const` block per module.

It's also possible for constants to be defined at compile time based on previous constants:

```
const {
    WIDTH=80,
    HEIGHT=32,
    FIELD_SIZE = (WIDTH+1)*(HEIGHT+1)
    DIVIDER_WIDTH = WIDTH+1
}
```

In this example, `FIELD_SIZE` would be defined as `2673`, and `DIVIDER_WIDTH` would be `81`.

## `class`

Defines a structure composed of various scalar primitives that can be addressed by name.

It will eventually become possible to attach methods to a class as well.

> ⚠ There is as yet no way to automatically assign class members on creation. This will become possible with an `__init__` class method.

```
class MyClass {
    x:i32,
    y:i32
}

def myfunc(x:myClass):i32{
    return x.x
}

def main(){
    var z:myClass
    z.x=1
    z.y=2
    q=myfunc(z)
}

```

## `def`

Define a function signature and its body.

```
def add(a,b){
    return a+b
}

```

The default type for function signatures and return types, as with variables, is `i32`.

Function signatures can also take explicitly specified types and a return type:

```
def add(a:u64, b:u64):u64{
    return a+b
}
```

## `extern`

Defines an external function with a C calling interface to be linked in at compile time.

An example, on Win32, that uses the `MessageBoxA` system call:

```
extern MessageBoxA(hwnd:i32, msg:ptr i8, caption:ptr i8, type: i8):i32

def main(){
    MessageBoxA(0,c_data('Hi'),c_data('Yo there'),0B)
}
```

## `pragma`

The `pragma` keyword defines a set of key-value pairs used by the compiler to guide the compilation process.

The keys and values must both be constants.

```
pragma {
    # these are the defaults
    loop_vectorize = True    
    opt_level = 3
    size_level = 0
    slp_vectorize = True
    unroll_loops = True
}
```

Right now the available options are little more than one-to-one correspondants to the optimization controls exposed through Aki's LLVM layer:

### `loop_vectorize`

A boolean value that indicates whether the compiler should use loop vectorization optimizations. Default is `True`.

### `opt_level`

An integer from 0 to 3 that indicates the overall optimization level for the compiler. Default is `3`.

### `size_level`

An integer from 0 to 2 that indicates how aggressively the compiler optimizes for program size. Default is `0`.

### `slp_vectorize`

A boolean value that indicates whether the compiler should apply SLP vectorization to loops. Default is `True`.

### `unroll_loops`

A boolean value that indicates whether the compiler should unroll loops for speed. Default is `True`.

## `unary`

The `unary` keyword is used in a function signature to define a unary operator, which uses any currently unreserved single character symbol.

> ⚠ This keyword and its functionality are likely to be removed from the language.

```
def unary $(val)
    return val+1

x = $x # example usage
```

## `uni`

A `uni` block defines *universals*, or variables available throughout a module. The syntax is the same as a `var` assignment.

There can be more than one `uni` block per module, typically after any  `const` module. This rule is not enforced by the compiler, but it's a good idea, since `uni` declarations may depend on previous `const` declarations.

```
uni {
    x=32,
    # defines an i32, the default variable type

    y=64U,
    # unsigned 64-bit integer

    z:byte=1B
    # explicitly defined byte variable,
    # set to an explicitly defined byte value

}
```

# Keywords

These keywords are valid within the body of a function.

## `break`

Exit a `loop` manually.

```
x=1
loop {
    x=x+1
    if x>10 then break
}
print (x)

[output:]

11
```

## `default`

See [`match`](#match).

## `if` / `then` / `elif` / `else`

If a given expression yields `True`, then yield the value of one expression; if `False`, yield the value of another. Each `then` clause is an expression.

```
y = 0
t = {if y == 1 then 1 elif y > 1 then 2 else 3}

```

**Each branch of an `if` must yield the same type.** For operations where the types of each decision might mismatch, or where some possible decisions might not yield a result at all, use [`when/then/elif/else`](#when).

`if` constructions can also be used for expressions where the value of the expression is to be discarded. 

```
# FizzBuzz

def main(){
    # Loops auto-increment by 1 if no incrementor is specified
    loop (x = 1, x < 101) {
        if x mod 15 == 0 then print ("FizzBuzz")
            elif x mod 3 == 0 then print ("Fizz")
            elif x mod 5 == 0 then print ("Buzz")
            else print (x)
    }
    return 0
}
```

Here, `print` yields the number of characters printed from the `loop` block, but that value is not actually used anywhere.

Note that if we didn't have the `return 0` at the bottom of `main`, the last value yielded by the `if` would be the value returned from `main`.


## `loop`

Defines a loop operation. The default is a loop that is infinite and needs to be exited manually with a `break`.

```
x=1
loop {
    print (x)
    x = x + 1
    if x>10: break
}
```

A loop can also specify a counter variable and a while-true condition:

```
loop (x = 1, x < 11){
    print (x)
}
```

The default incrementor for a loop is +1, but you can make the increment operation any valid operator for that variable.

```
loop (x = 100, x > 0, x - 5) {
    print (x)
}
```

If the loop variable is already defined in the current or universal scope, it is re-used. If it doesn't exist, it will be created and added to the current scope, and will continue to be available in the current scope after the loop exits.

If you want to constrain the use of the loop variable to only the loop, use `with`:

```
with x loop (x = 1, x < 11) {
    print (x)
} # x is not valid outside of this block
```

## `match`

Evaluates an expression based on whether or not a value matches one of a given set of compile-time constants (*not* expressions).

The value returned from this expression is the matched value, not any value returned by the expressions themselves.

There is no "fall-through" between cases, but you can combine cases by way of a comma-separated list of constants.

The `default` keyword indicates which expression to use if no other match can be found.

```
match t {
    0,1,2: break
    3,4: {
        t=t+1
        s=1
    }
    5,6: {
        t=0
        s=0
    }
    default: t=t-1
}
```

## `not`

A built-in unary for negating values.

```
x = 1
y = not x # 0
```

## `return`

Provides early exit from a function and returns a value. The value must match the function's return type signature.

```
def fn(x):u64{
    if x>1 then return 1U
        else return 0U
}
```

## `unsafe`

Designates an expression or block where direct manipulation of memory or some other potentially dangerous action is performed.

```
def main(){
    var x:i8[4]
    
    # Not unsafe because we're just obtaining a raw pointer.
    var y=c_ref(x[1])

    # Unsafe because we're modifying memory at that location.
    unsafe {
        c_ptr_mod(y,32)
    }

    x[1]
}

```

Running `main()` here would yield `32`.

`unsafe` can also work as an inline declaration as long as you're only designating a single expression as `unsafe`:

```
unsafe c_ptr_mod(y,32)
```

An example with a `print` function, where we pass a byte array:

```
var x=[65B,66B,67B,0B]
print(unsafe x)
```

yields `ABC`.

Note the terminating NULL in the array; the `print` statement makes no assumptions about whether the data is NULL-terminated when supplied with an `unsafe` parameter.

## `var`

Defines a variable for use within the scope of a function.

```
def main(){
    var x = 1, y = 2
    # implicit i32 variable and value
    # multiple variables are separated by commas

    var y = 2B
    # explicitly defined value: byte 2
    # variable type is set automatically by value type

    var z:u64 = 4U
    # explicitly defined variable: unsigned 64
    # with an explicitly defined value assigned to it
}
```

For a variable that only is valid within a specific scope in a function, use `with`.

## `while`

Defines a loop condition that continues as long as a given condition is true.

```
var x=0
while x<100 {
    x=x+1
}
```

## `with`

Provides a context, or closure, for variable assignments.

```
y=1 # y is valid from here on down

with var x = 32 {
    print (y)
    print (x)
    # but use of x is only valid in this block
}
```

As with variables generally, a variable name in a `with` block cannot "shadow" one outside.

```
y=1 
with var y = 2 { # this is invalid
    ...
}
```

## `when`

If a given expression yields `True`, then use the value of one expression; if `False`, use the value of another.

Differs from `if/then/else` in that the `else` clause is optional, and that the value yielded is that of the *deciding expression*, not the `then/else` expressions. This way, the values of the `then/else` expressions can be of entirely different types if needed.

```
when x=1 then
    do_something() # this function returns an u64
elif x=2 then
    do_something_else() # this function returns an i32
else do_yet_another_thing() # this function returns an i8
```

In all cases the above expression would return the value of whatever `x` was, not the value of any of the called functions.

# Decorators

Aki can use certain keywords prefaced with the `@` symbol to *decorate* a function or code block. Decorators are used to control compile- and runtime behaviors.

Here is an example of a decorated function:

```
@inline
def inline_func(){
    32
}
```

Multiple top-level expressions can be grouped together under a single decorator by simply enclosing them in a block expression:

```
@inline {
    def inline_func(){
        32
    }
    def other_inline_func(){
        64
    }
}
```

Here, both `inline_func` and `other_inline_func` will be decorated with `@inline`.

## `@inline`

Indicates that the decorated function is always to be inlined. Inlining replaces any calls to the function with the function body, to speed up the call process.

Functions defined as [`binary`](#binary) or [`unary`](#unary) are automatically inlined. To suppress this behavior, use `@noinline` on the operator definition.

A function decorated with `@inline` cannot be decorated with `@varfunc`, and vice versa.

A function decorated with `@inline` cannot be decorated with `@noinline`, and vice versa.

## `@noinline`

Indicates that the decorated function is never to be inlined. Inlining replaces any calls to the function with the function body, to speed up the call process.

Functions defined as [`binary`](#binary) or [`unary`](#unary) are automatically inlined. To suppress this behavior, use `@noinline` on the operator definition.

A function decorated with `@inline` cannot be decorated with `@noinline`, and vice versa.

## `@nomod`

Indicates that the compiler should assume the decorated function does not modify any of the arguments passed to it, such as a s tring's underlying data.

This allows functions that take in an object to not affect how that object's disposal tracking is calculated.

An entire function must be decorated with this. It is not possible to indicate that only some arguments of a function are not modified.

A `@varfunc`-decorated function cannot be decorated with `@nomod`.

## `@unsafe_req`

Indicates that the function in question can only be called from within an [`unsafe`](#unsafe) block.

## `@varfunc`

Designates a top-level function that can be assigned to a variable and invoked through the variable.

Normally functions cannot be handled this way; they must be specially decorated to do so.

```
@varfunc {
    def f1(a:i32):i32 {
        a+1
    }

    def f2(a:i32):i32 {
        a+2
    }
}

def main(){
    var f:func(i32):i32
    f=f1
    print (f(32))
    f=f2
    print (f(32))
}
```

This allows the functions `f1` and `f2` to be interchangeably assigned to the variable `f`, and allows `f` to be called as if it were a function itself. (The output from this program is the two numbers `33` and `34`.)

A function decorated with `@inline` cannot be decorated with `@varfunc`, and vice versa.

A `@varfunc`-decorated function cannot be decorated with `@nomod`.

# Builtin functions

The following built-ins are largely for the sake of interoperability with C, and for bootstrapping the language to full functionality.

> ⚠ These functions are likely to be highly unstable.

## `box` / `unbox`

Places a variable inside a box of type `obj`, or removes it from that box.

This is used to allow variables of potentially multiple types to be manipulated.

To determine the type of a variable inside an `obj` box, use `objtype()`.

```
def main(){    
    loop {
        print ("1) String\n2) i32\n3) u64\n4) quit\n> ", end='')
        
        var choice = i32(input())
        var x:obj

        match choice {
            1: x=box("Yo there!")
            2: x=box(32)
            3: x=box(32U)
            4: break
            default: pass
        }
        
        match objtype(x) {
            type(str): print ("String, with value:", unsafe unbox(x,str))
            type(i32): print ("Signed 32-bit integer!")
            type(u64): print ("Unsigned 64-bit integer!")
            default: print ("No idea!")
        }
    }
    0
}
```

## `c_addr`

Returns the location of an object in memory, as an integer. The bitwidth of the integer matches the platform in use.

## `c_alloc` / `c_free`

Allocate *n* bytes from the heap to a pointer; free bytes associated with a given pointer.

## `c_data`

Returns a pointer to the data component for an object, such as a string or an array. This can be used, for instance, to pass a pointer to a null-terminated string to a C library function that needs it.

This example uses `c_data` to pass raw string data to a Win32 system call:

```
extern MessageBoxA(hwnd:i32, msg:ptr i8, caption:ptr i8, type: i8):i32

def main(){
    MessageBoxA(0,c_data('Hi'),c_data('Yo there'),0B)
}
```

## `c_gep`

Provides an interface to LLVM's `getelementpointer` instruction; used for indexing into structures.

## `c_ref` / `c_deref`

`c_ref` returns a typed pointer to a scalar, like an int; `c_deref` dereferences such a pointer.


## `c_size`

Returns the size in bytes of a scalar type, or of the descriptor for an object. For a string, for instance, this would *not* be the length of the actual string data (for that, use `len`), but the size of the whole structure that describes a string.

```
var y:u64
x=c_size(u) # 8
```

## `c_obj_alloc` / `c_obj_free`

Allocates and then frees tracked space for an object defined by a specific type.

```
x=c_obj_alloc(u64[64])
```

This allocates the memory needed to store an array *object* (which includes various run-time metadata) containing 64 `u64`s.

The assigned variable is marked as tracked, and so the compiler will attempt to autodispose it when it goes out of scope.

By contrast, `c_alloc`:

* does not track for disposal
* only allocates a raw region of space of a certain number of bytes, not an object type

## `c_obj_ref` / `c_obj_deref`

Like `c_ref/c_deref`, but for complex objects like strings.

> ⚠ This may eventually be merged into `c_ref/c_deref` for simplicity.


## `c_ptr_int`

Converts a pointer to an integer of the length dictated by the platform (e.g., 64 bits for a platform with a 64-bit pointer size).

## `c_ptr_math`

Takes a pointer and adds to its position by the number of bytes specified. Returns a newly modifed pointer.

```
var x=32
var y=c_ref(x)
var z=c_ptr_math(y,1)
```

## `c_ptr_mod`

> ⚠ This requires the `unsafe` keyword.

Modifies the data at a given pointer location. Accepts only the same type as the pointer's type.

```
var x=32
var y=c_ref(x)
unsafe c_ptr_mod(y,128) # returns y with a modified underlying value
```

## `cast` / `convert`

`cast` casts one data type as another, such as a pointer to a u64, or an i8 to a u32. Ignores signing and truncates bitwidths without warning.

```
var x:i32
var y:u64=2000U
x = cast(y,i32)
```

`convert` converts data between primitive scalar value types, such as i8 to i32. Checks for signing and bitwidth, and does not truncate values.

```
var x:i32
var y:byte=32B
x = convert(y,i32)
```

## `objtype`

Returns a module-specific value that corresponds to a variable type held inside an `obj` container.

```
var x=obj("Hi there!")
objtype(x)==type(str)
```

## `ord`

Returns the ASCII (eventually UTF-8) codepoint of a single character.

```
ord("a")
```

yields `97`.

## `type`

Returns a module-specific value that corresponds to a variable type.

```
var x="Hi there!"
objtype(x)==type(str)
```


# Methods

## `len`

Returns the length of an object. This depends entirely on what the object is.

For a string, this would be the size of the underlying string data in bytes, including the terminating null.

```
len("Hi!")
```
yields `4`.


# Library functions

## `inkey`

Waits indefinitely for a keypress from the console, then returns a byte value that corresponds to the character returned.

```
var x:byte
x=inkey()

var y=inkey() # you can also just say this

```

## `print`

Prints a scalar type or a string to the console.

```
print ("Hello world!")
var x=5
print (x)
var y=3.1415
print (y)
```

> ⚠ `print` currently takes only one argument.

# Types:

## `bool (u1)`

An unsigned bit (true or false).

Constant representation of 1: `1b`

Note that any number assigned a `bool` type will only have the first bit of the number evaluated. Therefore, `2b` is `False`, but `3b` is `True`.

## `byte (u8)`

An unsigned byte.

Constant representation of 1: `1B`

## `i8/16/32/64`

Signed integers of 8, 16, 32, or 64 bit widths.

Constant representation of 1: `1b, 1i, 1u`

The default variable type is a 32-bit signed integer (`1i`).

## `u8/16/32/64`

Unsigned integers of 8, 16, 32, or 64 bit widths.

Constant representation of 1: `1B, 1I, 1U`

## `f32/64`

Floats of 32 or 64 bit widths: `3.2f`/ `3.2F`.

Constant representation of 1: `1.` or `1.0`.

## `array`

An array of scalar (integer or float) types.

For a one-dimensional array of bytes:

`var x:byte[100]`

For a multidimensional array of bytes:

`var x:byte[32,32]`

> ⚠ There is as yet no way to define array members on creation. They have to be assigned individually.

> ⚠ There is as yet no way to nest different scalars in different array dimensions.

> ⚠ There is as yet no way to perform array slicing or concantenation.

## `obj`

A container for types. Use [`box()` and `unbox()`](#box--unbox) to place variables inside an `obj` box.

## `str`

A string of characters, defined either at compile time or runtime.

```
hello = "Hello World!"
hello_also = 'Hello world!'
hello_again = 'Hello
world!'
```

Linebreaks inside strings are permitted. Single or double quotes can be used as long as they match.

String escaping functions are not yet robustly defined, but you can use `\n` in a string for a newline, and you can escape quotes as needed with a backslash as well:

```
hello = "Hello \"world\"! \n"
```

The `str()` function can create a new string at runtime, and accepts the following forms of input:

* A pointer to a null-terminated string.
* An `i32` (other scalar types to follow later).

The `input()` builtin returns a `str` object.

```
var x:str
x=input()

var y=str() # y is now an empty string of type `str`

```

> ⚠ There is as yet no way to perform string slicing or concantenation.


## `ptr`

Type prefix to indicate the value in question is a pointer to the stated type, e.g. `var x:ptr i32`. This is currently used mainly in library functions and demos, so its casual use isn't recommended.