# These functions convert a function name into its "mangled" eqivalent
# based on its type signature, to allow for multiple dispatch.

# TODO: All of the codexec functions should also go through here

# new mangle type:
# ! for separator, v_id for id (i32, etc.), and commas to separate each v_id
# this allows custom typedefs as well

mangle_separator = '@'
mangle_delineator = '@'


def mangle_funcname(name, type):
    m_list = []
    for n in type.args:
        m_list.append(n.v_id + mangle_delineator)
    return f"{name}{mangle_separator}{''.join(m_list)}"


def mangle_function(func):
    func.public_name = func.name
    func.name = mangle_types(func.name, func.args)
    return func


def mangle_call(name, args):
    return name + mangle_args(args)


def mangle_args(args):
    return mangle_separator + ''.join(
        [n.v_id + mangle_delineator for n in args])


def mangle_types(name, args):
    return name + mangle_separator + ''.join(
        [n.type.v_id + mangle_delineator for n in args])