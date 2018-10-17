# How Aki handles memory

This document describes how Aki will *eventually* manage memory.

## Universals (`uni`) of any kind

Universals are statically created at compile time and thus do not need to be memory-managed.

## Manually allocated objects

Anything allocated with `c_alloc` is your responsibility. You must `c_free` such things yourself.

## Scalars (`int`, etc.)

Any *scalar* allocated in a function is automatically disposed as the end of a function.

Scalars can be passed directly between functions as-is with no memory management implications.

## Objects (arrays, strings, etc.)

Objects are tracked at runtime using reference counting, and are disposed automatically when they go out of scope and their references drop to zero.

In time, I plan to add code analysis tools that allow you to determine when and if objects can be statically tracked at compile time, so that they don't have to be refcounted.

The following describes some of my older strategies for tracking, which may still be relevant.

### Tracking

Any *object* created in a function is by default tagged as "trackable," meaning the compiler traces its behavior and automatically disposes of it when it goes out of scope. This typically is the case when the object reaches the end of the function without being returned or otherwise given away.

If an object is *returned* from a function, the function is marked by the compiler with the `@track` decorator, which indicates that anything returned from that function should be tracked.

(Note: If you manually allocate objects by way of `c_alloc`, and return those objects from their originating function, you can ensure those objects are tracked by decorating that function with `@track`.)

### Giveaways

If an object is used as an argument in a function call, it's considered "given away" and is unmarked for tracking. 

*However*, if the object is given away to a function marked as `@no_mod`, this doesn't apply.

`@no_mod` indicates that the function in question, and all its descendents, do not modify their inputs in any way. Any standard library function will have proper use of `@no_mod` to indicate object safety for anything passed to it; however, it's applied at the programmer's discretion.

> *A proposed future enhancement:* The compiler will provide you with feedback about which objects are untracked, and at what point objects are removed from tracking (e.g., when they're used as a call argument). The compiler should also provide you with feedback if a given function does or doesn't modify its inputs, as a way to ensure `@no_mod` is a proper designation. The long-term idea would be to have `@no_mod` applied automatically as often as possible.

> *A proposed future enhancement:* One way to ensure any variable is disposed is to enclose it in a `with` block, since all variables created in that scope are automatically disposed at the end. However, any object created in that scope *cannot* be given away, except to `@no_mod` functions or as a copy. (This is pending a standard mechanism for making object copies, like a `__copy__` method.)

----

One thing I'm trying to aim for is to minimize the amount of memory management work that has to be done when using "out of the box" things. If you just use the standard library and write programs that are essentially glorified scripts, manual memory management shouldn't enter the picture. For more complex programs, you'll need to do *some* work, but not as much. And if you want to go with manual memory management all the way, you can do that too.

In short, the amount of memory management work to be done should be proportionate to the complexity of the job, and made convenient whenever possible.