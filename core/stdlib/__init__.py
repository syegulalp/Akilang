import llvmlite.ir as ir
from core.mangling import mangle_call, mangle_funcname

def makefunc(module, func_name, func_type, func_sig, no_mangle=False):
    func_s = ir.FunctionType(func_type, func_sig)
    if no_mangle:
        m_name = func_name
    else:
        m_name = mangle_funcname(func_name, func_s)

    func = ir.Function(module, func_s, m_name)    
    func.attributes.add('nonlazybind')
    func.linkage = 'private'

    irbuilder = ir.IRBuilder(func.append_basic_block('entry'))
    return func, irbuilder


def makecall(irbuilder, module, funcname, func_sig):

    # we might want to use the node visitor,
    # since that also supplies things like
    # decorator tests, etc.

    types = [v.type for v in func_sig]
    f_name = module.globals.get(
        mangle_call(funcname, types)
    )
    return irbuilder.call(
        f_name,
        func_sig
    )