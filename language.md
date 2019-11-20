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
  - [`const`](#const)
  - [`def`](#def)
  - [`extern`](#extern)
  - [`uni`](#uni)
- [Keywords](#keywords)
  - [`break`](#break)
  - [`default`](#default)
  - [`if` / `else`](#if--else)
  - [`loop`](#loop)
  - [`not`](#not)
  - [`return`](#return)
  - [`select`/`case`](#selectcase)
  - [`unsafe`](#unsafe)
  - [`var`](#var)
  - [`while`](#while)
  - [`with`](#with)
  - [`when`](#when)
- [Types:](#types)
  - [`bool (u1)`](#bool-u1)
  - [`byte (u8)`](#byte-u8)
  - [`i8/32/64`](#i83264)
  - [`u8/32/64`](#u83264)
  - [`f32/64`](#f3264)
  - [`array`](#array)
  - [`str`](#str)

# Aki language basics

This is a document of Aki syntax and usage.

> ⚠ This document is incomplete and is being revised continuously.

# Introduction

## Expressions

Expressions are the basic unit of computation in Aki. Each expression returns a value of a specific type. Every statement is itself an expression:

```
5
```

is an expression that returns the value `5`. (The type of this value is the default type for numerical values in Aki, which is a signed 32-bit integer.)

```
print (if x==1 'Yes' else 'No')
```

Here, the argument to `print` is an expression that returns one of two compile-time strings depending on the variable `x`. (`print` itself is a wrapper for `printf` and so returns the number of bytes printed.)

The divisions between expressions are normally deduced automatically by the compiler. You can  use parentheses to explicitly set expressions apart:

```
(x+y)/(a+b)
```

The whole of the above is also considered a single expression.

You can also use a semicolon to separate expressions:

```
x+y; a+b;
```

Function bodies are considered expressions:

```
def myfunc() 5
```

This defines a function, `myfunc`, which takes no arguments, and returns `5` when invoked by `myfunc()` elsewhere in the code.

To group together one or more expressions procedurally, for instance as a clause in an expression or in the body of a function, use curly braces to form a *block*:

```
def main(){
    print ("Hello!")
    var x=invoke()
    x+=1
    x
}
```

With any expression block, the last expression is the one returned from the block. To that end, the `x` as the last line of the function body here works as an *implicit return.* You could also say:

```
def main(){
    print ("Hello!")
    var x=invoke()
    x+=1
    return x
}
```

For the most part, Aki does not care about where you place linebreaks, and is insensitive to indentation. Expressions and strings can span multiple lines. Again, if you want to forcibly separate lines into expressions, you can use semicolons.

However, comments (anything starting with a `#`) always end with a linebreak.

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
    var x = (if x>0 1 else -1)
    x * 5
}
```

Functions can also take optional arguments with defaults:

```
def f1(x:i32, y:i32=1) x+y
```

Invoking this with `f1(0,32)` would return `32`. With `f1(1)`, you'd get `2`.

Note that optional arguments must always follow mandatory arguments.


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
extern MessageBoxA(hwnd:i32, msg:ptr i8, caption:ptr i8, msg_type: i8):i32

def main(){
    MessageBoxA(0,c_data('Hi'),c_data('Yo there'),0:byte)
}

```

## `uni`

A `uni` block defines *universals*, or variables available throughout a module. The syntax is the same as a `var` assignment.

There can be more than one `uni` block per module, typically after any  `const` module. This rule is not enforced by the compiler, but it's a good idea, since `uni` declarations may depend on previous `const` declarations.

```
uni {
    x=32,
    # defines an i32, the default variable type

    y=64:u64,
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
    x+=1
    if x>10 break
}
x

[output:]

11
```

## `default`

See [`match`](#match).

## `if` /  `else`

If a given expression yields `True`, then yield the value of one expression; if `False`, yield the value of another. Each `then` clause is an expression.

```
var y = 0
var t = {if y == 1 2 else 3}

```

**Each branch of an `if` must yield the same type.** For operations where the types of each decision might mismatch, or where some possible decisions might not yield a result at all, use [`when/then/else`](#when).

`if` constructions can also be used for expressions where the value of the expression is to be discarded. 

```
# FizzBuzz

def main(){
    # Loops auto-increment by 1 if no incrementor is specified
    loop (var x = 1, x < 101) {
        if x % 15 == 0 print ("FizzBuzz")
            else if x % 3 == 0  print ("Fizz")
            else if x % 5 == 0  print ("Buzz")
            else printf_s(c_data('%i\n'),x)
    }
    0
}
```

Note that if we didn't have the `return 0` at the bottom of `main`, the last value yielded by the `if` would be the value returned from `main`.


## `loop`

Defines a loop operation. The default is a loop that is infinite and needs to be exited manually with a `break`.

```
x=1
loop {
    x = x + 1
    if x>10: break
}
```

A loop can also specify a counter variable and a while-true condition:

```
loop (x = 1, x < 11){
    ...
}
```

The default incrementor for a loop is +1, but you can make the increment operation any valid operator for that variable.

```
loop (x = 100, x > 0, x - 5) {
    ...
}
```

If the loop variable is already defined in the current or universal scope, it is re-used. If it doesn't exist, it will be created and added to the current scope, and will continue to be available in the current scope after the loop exits.

If you want to constrain the use of the loop variable to only the loop, use `with`:

```
with x loop (x = 1, x < 11) {
    ...
} # x is not valid outside of this block
```

## `not`

A built-in unary for negating values.

```
x = 1
y = not x # 0
```

## `return`

Exits from a function early and returns a value.

```
def f1(x):str {
    if x == 1 return "Yes"
    # else ...
    "No"
}
```

Note that the return value's type must match the function's overall type, and that all returns must have the same type. This is not permitted:

```
def f1(x) {
    if x == 1 return "Yes"
    # else ...
    5
}
```

This, however, is okay. Note how the function has no explicit return type, but all the returned values have matching types.

```
def f1(x) {
    if x == 1 return "Yes"
    # else ...
    "No"
}
```


## `select`/`case`

Evaluates an expression based on whether or not a value is equal to one of a given set of compile-time constants (*not* expressions).

The value returned from this expression is the selected value, *not any value returned by the expressions themselves.*

There is no "fall-through" between cases

The `default` keyword indicates which expression to use if no other match can be found.

```
select t {
    case 0: break
    case 1: {
        t+=1
        s=1
    }
    case 2: {
        t=0
        s=0
    }
    default: t-=1
}
```

## `unsafe`

Designates an expression or block where direct manipulation of memory or some other potentially dangerous action is performed.

This is not widely used yet.


## `var`

Defines a variable for use within the scope of a function.

```
def main(){
    var x = 1, y = 2
    # implicit i32 variable and value
    # multiple variables are separated by commas

    var y = 2:byte
    # explicitly defined value: byte 2
    # variable type is set automatically by value type

    var z:u64 = 4:u64
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
    x+=1
}
```

## `with`

Provides a context, or closure, for variable assignments.

```
y=1 # y is valid from here on down

with var x = 32 {
    y+x
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
when x=1 do_something() # this function returns an u64
else if x=2 do_something_else() # this function returns an i32
else do_yet_another_thing() # this function returns an i8
```

In all cases the above expression would return the value of whatever `x` was, not the value of any of the called functions.

# Types:

## `bool (u1)`

An unsigned true or false value.

Constant representation of 1: `1:bool`

## `byte (u8)`

An unsigned byte.

Constant representation of 1: `1:byte`

## `i8/32/64`

Signed integers of 8, 32, or 64 bit widths.

Constant representation of 1: `1:i8, 1:i32, 1:i64`

The default variable type is a 32-bit signed integer (`1:i32`).

## `u8/32/64`

Unsigned integers of 8, 32, or 64 bit widths.

Constant representation of 1: `1:u8, 1:u32, 1:u64`

## `f32/64`

Floats of 32 or 64 bit widths: `3.2:f32`/ `3.2:f64`.

Constant representation of 1: `1.` or `1.0`.

## `array`

An array of scalar (integer or float) types.

For a one-dimensional array of bytes:

`var x:array byte[100]`

For a multidimensional array of bytes:

`var x:array byte[32,32]`

> ⚠ There is as yet no way to define array members on creation. They have to be assigned individually.

> ⚠ There is as yet no way to nest different scalars in different array dimensions.

> ⚠ There is as yet no way to perform array slicing or concatenation.

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

> ⚠ There is as yet no way to perform string slicing or concantenation.