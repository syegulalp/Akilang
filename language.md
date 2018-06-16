# Aki language basics

This is a document of Aki syntax and usage.

> ⚠ This document is incomplete and is being revised continuously.

- [Aki language basics](#aki-language-basics)
- [Introduction](#introduction)
    - [Expressions](#expressions)
    - [Functions and function calls](#functions-and-function-calls)
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
    - [binary](#binary)
    - [const](#const)
    - [class](#class)
    - [def](#def)
    - [extern](#extern)
    - [unary](#unary)
    - [uni](#uni)
- [Keywords](#keywords)
    - [break](#break)
    - [default](#default)
    - [if / then / elif / else](#if--then--elif--else)
    - [loop](#loop)
    - [match](#match)
    - [not](#not)
    - [return](#return)
    - [var](#var)
    - [while](#while)
    - [with](#with)
    - [when](#when)
- [Decorators](#decorators)
    - [@inline](#inline)
    - [@noinline](#noinline)
    - [@varfunc](#varfunc)
- [Builtin functions](#builtin-functions)
    - [c_addr](#c_addr)
    - [c_alloc / c_free](#c_alloc--c_free)
    - [c_obj_alloc / c_obj_dealloc](#c_obj_alloc--c_obj_dealloc)
    - [c_data](#c_data)
    - [c_size](#c_size)
    - [c_array_ptr](#c_array_ptr)
    - [c_ref / c_deref](#c_ref--c_deref)
    - [c_obj_ref / c_obj_deref](#c_obj_ref--c_obj_deref)
    - [cast/convert](#castconvert)
- [len](#len)
- [Library functions](#library-functions)
    - [inkey](#inkey)
    - [print](#print)
- [Types:](#types)
    - [bool (u1)](#bool-u1)
    - [byte (u8)](#byte-u8)
    - [i8/32/64](#i83264)
    - [u8/32/64](#u83264)
    - [f64](#f64)
    - [array](#array)
    - [str](#str)
    - [ptr](#ptr)

# Introduction

## Expressions

Expressions are the basic unit of computation in Aki. Each expression returns a value of a specific type. Every statement is itself an expression:

```
5
```

is an expression that returns the value 5. (The type of this value is the default type for numerical values in Aki, which is a signed 32-bit integer.)

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

* a name that does not shadow any existing name or keyword (except for functions with varying type signatures, where the same name can be reused)
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

## Variables and variable typing

There is no shadowing of variable names permitted anywhere. You cannot have the same name for a variable in both the universal and current scope.

Scalar types -- integers, floats, booleans -- are passed by value. All other objects (classes, strings, etc.) are passed by reference, by way of a pointer to the object.

## Symbols

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

## `and`/`or`/`xor`/`not` operators

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


## binary 

The `binary` keyword is used in a function signature to define a binary operator, with an optional precedence.

From the standard library:

```
def binary mod 10 (lhs, rhs)
    lhs - rhs * (lhs/rhs)
```

This defines a binary named `mod` (equivalent to the `%` operator in Python).

The `10` is the operator precedence, with lower numbers having higher precedence.

## const

A `const` block is used to define compile-time constants for a module. Right now only numerical constants can be defined. There is currently no constant folding in the compiler, however, so expressions involving multiple constants are not consolidated into a single constant (yet).

There should only be one `const` block per module, at the top, but this rule is not strictly enforced by the compiler; it's just good etiquette.

```
const {
    x=10,
    y=20
}

def main(){
    print (x+5) # x becomes 10 at compile time, so this is always 15
}
```


## class

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

## def

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

## extern

Defines an external function to be linked in at compile time.

An example, on Win32, that uses the `MessageBoxA` system call:

```
extern MessageBoxA(hwnd:i32, msg:ptr i8, caption:ptr i8, type: i8):i32

def main(){
    MessageBoxA(0,c_data('Hi'),c_data('Yo there'),0B)
}
```

## unary

The `unary` keyword is used in a function signature to define a unary operator, which uses any currently unreserved single character symbol.

> ⚠ This keyword and its functionality are likely to be removed from the language.

```
def unary $(val)
    return val+1

# usage

x = $x
```

## uni

A `uni` block defines *universals*, or variables available throughout a module. The syntax is the same as a `var` assignment.

There should only be one `uni` block per module, just after any `const` module. This rule is not enforced by the compiler, but it's a good idea, since `uni` declarations may depend on previous `const` declarations.

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

## break

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

## default

See [`match`](#match).

## if / then / elif / else

If a given expression yields `True`, then yield the value of one expression; if `False`, yield the value of another. Each `then` clause is an expression.

```
y = 0
t = {if y == 1 then 1 elif y > 1 then 2 else 3}

```

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

Here, `print` yields the number of characters printed, but in this example it's not used for anything.

Note that if we didn't have the `return 0` at the bottom of `main`, the last value yielded by the `if` would be the value returned from `main`.

**Each branch of an if must yield the same type.** For operations where the types of each decision might mismatch, or where some possible decisions might not yield a result at all, use [`when/then/elif/else`](#when).

## loop

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
}
# x is not valid outside of this block
```

## match

Evaluates an expression based on whether or not a value matches one of a given set of constants (*not* expressions).

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

## not

A built-in unary for negating values.

```
x = 1
y = not x # 0
```

## return

Provides early exit from a function and returns a value. The value must match the function's return type signature.

```
def fn(x):u64{
    if x>1 then return 1U
        else return 0U
}
```

## var

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

## while

Defines a loop condition that continues as long as a given condition is true.

```
var x=0
while x<100 {
    x=x+1
}
```

## with

Provides a context, or closure, for variable assignments.

```
y=1
# y is valid from here on down

with var x = 32 {
    print (y)
    print (x)
    # but use of x is only valid in this block
}
```

As with variables generally, a variable name in a `with` block cannot "shadow" one outside.

```
# this is invalid
y=1
with var y = 2 {
    ...
}
```

## when 

If a given expression yields `True`, then use the value of one expression; if `False`, use the value of another.

Differs from `if/then/else` in that the `else` clause is optional, and that the value yielded is that of the *deciding expression*, not the `then/else` expressions.

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

## @inline

Indicates that the decorated function is always to be inlined. Inlining replaces any calls to the function with the function body, to speed up the call process.

Functions defined as [`binary`](#binary) or [`unary`](#unary) are automatically inlined. To suppress this behavior, use `@noinline` on the operator definition.

A function decorated with `@inline` cannot be decorated with `@varfunc`, and vice versa.

A function decorated with `@inline` cannot be decorated with `@noinline`, and vice versa.

## @noinline

Indicates that the decorated function is never to be inlined. Inlining replaces any calls to the function with the function body, to speed up the call process.

Functions defined as [`binary`](#binary) or [`unary`](#unary) are automatically inlined. To suppress this behavior, use `@noinline` on the operator definition.

A function decorated with `@inline` cannot be decorated with `@noinline`, and vice versa.


## @varfunc

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

# Builtin functions

The following built-ins are largely for the sake of interoperability with C, and for bootstrapping the language to full functionality.

## c_addr

Returns the location of an object in memory, as an integer. The bitwidth of the integer matches the platform in use.

## c_alloc / c_free

Allocate *n* bytes from the heap to a pointer; free bytes associated with a given pointer.

## c_obj_alloc / c_obj_dealloc

> ⚠ This function's implementation is unstable and likely to change.

Same as above but takes a specific object type. Right now this is done by way of supplying a sample object through a closure:

```
x=c_obj_alloc({with var q:u64[64] q})
```

This allocates the memory needed to store a single object of `q`'s type.

## c_data

Returns a pointer to the data component for an object, such as a string or an array. This can be used, for instance, to pass a pointer to a null-terminated string to a C library function that needs it.

```
extern MessageBoxA(hwnd:i32, msg:ptr i8, caption:ptr i8, type: i8):i32

def main(){
    MessageBoxA(0,c_data('Hi'),c_data('Yo there'),0B)
}
```

## c_size

Returns the size in bytes of a scalar type, or of the descriptor for an object. For a string, for instance, this would *not* be the length of the actual string data (for that, use `len`), but the size of the whole structure that describes a string.

```
var y:u64
x=c_size(u) # 8
```

## c_array_ptr

Returns a raw u8 pointer to the start of an array or structure.

> ⚠ This function is likely to be removed.

## c_ref / c_deref

`c_ref` returns a typed pointer to a scalar, like an int; `c_deref` dereferences such a pointer.

## c_obj_ref / c_obj_deref

Like `c_ref/c_deref`, but for complex objects like strings.

> ⚠ This may eventually be merged into `c_ref/c_deref` for simplicity.


## cast/convert

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

# len

Returns the length of an object's actual data. For a string, this would be the size of the underlying string data in bytes, including the terminating null.

```
len("Hi!")
```
yields `4`.

Eventually, this will yield the results of an object's `__len__` method, when those are implemented.


# Library functions

## inkey

Waits indefinitely for a keypress from the console, then returns a byte value that corresponds to the character returned.

```
var x:byte
x=inkey()
```

## print

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

## bool (u1)

An unsigned bit (true or false).

Constant representation of 1: `1b`

## byte (u8)

An unsigned byte.

Constant representation of 1: `1B`

## i8/32/64

Signed integers of 8, 32, or 64 bit widths.

Constant representation of 1: `1b, 1i, 1u`

The default variable type is a 32-bit signed integer (`1i`).

## u8/32/64

Unsigned integers of 8, 32, or 64 bit widths.

Constant representation of 1: `1B, 1I, 1U`

## f64

Floats of 64 bit widths.

Constant representation of 1: `1.` or `1.0`.

## array

An array of scalar (integer or float) types.

For a one-dimensional array of bytes:

`var x:byte[100]`

For a multidimensional array of bytes:

`var x:byte[32,32]`

> ⚠ There is as yet no way to define array members on creation. They have to be assigned individually.

> ⚠ There is as yet no way to nest different scalars in different array dimensions.

> ⚠ There is as yet no way to perform array slicing or concantenation.

## str

A constant string, defined at compile time:

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

> ⚠ There is as yet no way to perform string slicing or concantenation.

> ⚠ There is as yet no way to create strings from user input.

## ptr

Type prefix to indicate the value in question is a pointer to the stated type, e.g. `var x=ptr i32`. This is currently used mainly in library functions and demos, so its casual use isn't recommended.