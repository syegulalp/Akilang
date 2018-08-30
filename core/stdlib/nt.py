import llvmlite.ir as ir
from core.vartypes import ArrayClass, VarTypes
from core.mangling import mangle_function, mangle_call

def makefunc(module, func_name, func_type, func_sig):
    func_s = ir.FunctionType(func_type, func_sig)
    func = mangle_function(ir.Function(module, func_s, func_name))
    func.attributes.add('nonlazybind')
    func.linkage='private'
    irbuilder = ir.IRBuilder(func.append_basic_block('entry'))
    return func, irbuilder

def stdlib(self, module):

    # TODO: emit all this as bitcode, save it

    # self.codegen gives us access to codegen methods if we need it

    
    
    # string length

    strlen, irbuilder = makefunc(
        module,
        '.object.str.__len__',
        VarTypes.u32, [VarTypes.str.as_pointer()]
    )

    # extract element 0, the length
    
    s1 = strlen.args[0]    
    s2 = irbuilder.gep(s1,
        [ir.Constant(ir.IntType(32), 0),
        ir.Constant(ir.IntType(32), 0),]
    )
    s3 = irbuilder.load(s2)

    irbuilder.ret(s3)

def stdlib_post(self, module):

    # This is all the instructions that have to come AFTER
    # the platform libraries are loaded
    # for instance, because we don't know how malloc or free work

    # del for array

    obj_del, irbuilder = makefunc(
        module,
        '.object.array_u64.__del__', VarTypes.bool,
        [VarTypes.u_size.as_pointer()]
    )
    
    # fn = ir.Function(module,
    #     ir.FunctionType(VarTypes.bool, [VarTypes.u_size]),
    #     mangle_call('c_free',[VarTypes.u_size])
    # )

    target = irbuilder.ptrtoint(obj_del.args[0], VarTypes.u_size)

    result = irbuilder.call(
        module.globals.get(mangle_call('c_free',[VarTypes.u_size])),
        [target]
    )

    irbuilder.ret(result)

    # new string from i32:

    # strlen, irbuilder = makefunc(
    #     module,
    #     '.object.str.__new__', VarTypes.str.as_pointer(),   
    #     [VarTypes.i32]
    # )

    # use win32 int to str or just snprintf?
    # see https://docs.microsoft.com/en-us/cpp/c-runtime-library/reference/itoa-s-itow-s
    # we also need to get resulting string length to store
    # https://docs.microsoft.com/en-us/cpp/c-runtime-library/reference/strnlen-strnlen-s

    # we should be able to automate creation of all the 
    # primitive scalar types to string

    # new string from raw u_size:
    # copy original array, add NUL
    # we don't want to mess with the original if we can help it

    # for in-place printing, we need to check that the last
    # character of the array is a NUL