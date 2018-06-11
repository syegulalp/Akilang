# What's next?

This is a short list of things I'm going to be working on, in rough order of attempt.

* Some form of tracing of object scopes, so that heap allocated objects can be passed freely around and deallocated intelligently

* Methods for dynamically allocating and manipulating strings. Right now all strings are statically allocated as globals at runtime.

* Constant folding in the parser. (*Implemented.*) 

* Adding class methods, for things like adding length-getting, slice-getting, iteration, and other common properties. (*Extremely basic version implemented.*)

* Function pointers, for better compatibility with C libraries. (*Present, but untested.*)

[Everything after that](mvp.md) is too far down the road to talk about, but I am at least thinking about it.