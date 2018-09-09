from core.vartypes import ArrayClass, VarTypes
from core.mangling import mangle_function, mangle_call, mangle_funcname

import llvmlite.ir as ir


def makefunc(module, func_name, func_type, func_sig, no_mangle=False):
    func_s = ir.FunctionType(func_type, func_sig)
    if no_mangle:
        m_name = func_name
    else:
        m_name = mangle_funcname(func_name, func_s)

    func = ir.Function(module, func_s, m_name)
    
    func.attributes.add('nonlazybind')
    func.linkage = 'private'
    func.decorators = []
    # TODO: override ir.Function __init__ to add decorators

    irbuilder = ir.IRBuilder(func.append_basic_block('entry'))
    return func, irbuilder


def makecall(irbuilder, module, funcname, func_sig):
    types = [v.type for v in func_sig]
    f_name = module.globals.get(
        mangle_call(funcname, types)
    )
    return irbuilder.call(
        f_name,
        func_sig
    )


def stdlib_post(self, module):

    # This is all the instructions that have to come AFTER
    # the platform libraries are loaded
    # for instance, because we don't know how malloc or free work

    #
    # len for string object
    #

    strlen, irbuilder = makefunc(
        module,
        '.object.str.__len__',
        VarTypes.u64, [VarTypes.str.as_pointer()]
    )

    s1 = strlen.args[0]
    s2 = irbuilder.gep(
        s1,
        [self.codegen._i32(0),
         self.codegen._i32(0), ]
    )
    s3 = irbuilder.load(s2)

    irbuilder.ret(s3)

    # del for array:

    obj_del, irbuilder = makefunc(
        module,
        '.object.array_u64.__del__', VarTypes.bool,
        [VarTypes.array(VarTypes.u64,0).as_pointer()]
    )

    ptr_cast = irbuilder.bitcast(
        obj_del.args[0],
        VarTypes.u_mem.as_pointer()
    )    

    result = makecall(
        irbuilder, module,
        'c_free',
        [ptr_cast]
    )

    irbuilder.ret(result)

    #
    # del for string
    #

    obj_del, irbuilder = makefunc(
        module,
        '.object.str.__del__', VarTypes.bool,
        [VarTypes.str.as_pointer()],
        no_mangle = True
    )

    # this just deletes the string object,
    # not the string data (for now)

    ptr_cast = irbuilder.bitcast(
        obj_del.args[0],
        VarTypes.u_mem.as_pointer()
    )

    # is there any way to determine at compile time
    # whether or not we need to delete the underlying data?

    #data_ptr = 

    result = makecall(
        irbuilder, module,
        'c_free',
        [ptr_cast]
    )

    irbuilder.ret(result)

    #
    # new string from raw pointer:
    #

    str_fn, irbuilder = makefunc(
        module,
        '.object.str.__new__', VarTypes.str.as_pointer(),
        [VarTypes.u_mem.as_pointer()]
    )

    str_ptr = str_fn.args[0]

    # XXX: unsafe
    # if we are doing this from an array or buffer,
    # we need to pass the max dimensions of the buffer

    str_len = makecall(
        irbuilder, module,
        'c_strlen',
        [str_ptr]
    )

    # Use the ABI to determine the size of the string structure

    size_of_struct = ir.Constant(
        VarTypes.u64,
        self.codegen._obj_size_type(
            VarTypes.str
        )
    )

    # Allocate memory for one string structure

    struct_alloc = makecall(
        irbuilder, module,
        'c_alloc',
        [size_of_struct]
    )

    # Bitcast the pointer to the string structure
    # so it's the correct type

    struct_reference = irbuilder.bitcast(
        struct_alloc,
        VarTypes.str.as_pointer()
    )

    # Obtain element 0, length.

    size_ptr = irbuilder.gep(
        struct_reference,
        [self.codegen._i32(0), self.codegen._i32(0)]
    )

    # Set the length

    irbuilder.store(
        str_len,
        size_ptr
    )

    # Obtain element 1, the pointer to the data

    data_ptr = irbuilder.gep(
        struct_reference,
        [self.codegen._i32(0), self.codegen._i32(1)]
    )

    # Set the data, return the object

    str_ptr_conv = irbuilder.bitcast(
        str_ptr,
        VarTypes.i8.as_pointer()
    )

    irbuilder.store(
        str_ptr_conv,
        data_ptr
    )

    # Note that we do not add tracking information
    # to this string yet.

    irbuilder.ret(struct_reference)

    #
    # new string from i32
    #

    str_fn, irbuilder = makefunc(
        module,
        '.object.str.__new__', VarTypes.str.as_pointer(),
        [VarTypes.i32]
    )

    result = makecall(
        irbuilder, module,
        'int_to_c_str',
        [str_fn.args[0]]
    )

    result = makecall(
        irbuilder, module,
        '.object.str.__new__',
        [result]
    )

    str_fn.tracked = True
    str_fn.do_not_allocate = True

    irbuilder.ret(result)

    #
    # new i32 from string
    #

    str_fn, irbuilder = makefunc(
        module,
        '.i32.__new__', VarTypes.i32,
        [VarTypes.str.as_pointer()]
    )    

    result = makecall(
        irbuilder, module,
        'c_str_to_int',
        [str_fn.args[0]]
    )    

    irbuilder.ret(result)