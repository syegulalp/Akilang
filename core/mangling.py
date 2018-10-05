F# These functions convert a function name into its "mangled" eqivalent
# based on its type signature, to allow for multiple dispatch.

# new mangle type:
# ! for separator, v_id for id (i32, etc.), and commas to separate each v_id
# this allows custom typedefs as well

mangle_separator = '@'
mangle_delineator = '@'
mangle_opt_separator = '|'


# Mangle a function supplied as an instance of ir.Function.
# This is used mainly for codegenning the internal stdlib.
def mangle_function(func):
    func.public_name = func.name
    func.name = mangle_types(func.name, func.args)
    return func

# Mangle a function based on its name and type signature.
def mangle_funcname(name, type):
    return mangle_call(name, type.args)

# Mangle a function call based on its name and a list of types.
def mangle_call(name, args):
    return f'{name}{mangle_args(args)}'

# Mangle only the arguments for a function
def mangle_args(args):
    return _mangle_args(args, mangle_delineator)


# Mangle only the optional arguments for a function
def mangle_optional_args(args):
    return _mangle_args(args, mangle_opt_separator)


def _mangle_args(args, sep):
    return sep + ''.join(
        [n.v_id + mangle_delineator for n in args])

# Mangle a function based on its name and a list of arguments.
def mangle_types(name, args):
    return name + mangle_separator + ''.join(
        [n.type.v_id + mangle_delineator for n in args])
