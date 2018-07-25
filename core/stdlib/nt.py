def stdlib(self, module):

    # TODO: emit all this as bitcode

    import llvmlite.ir as ir
    
    from core.vartypes import VarTypes
    from core.mangling import mangle_function

    # string length
    # eventually when we move string to an identified type, we can remove this.

    strlen_s = ir.FunctionType(VarTypes.u32, [VarTypes.str.as_pointer()])
    strlen = mangle_function(ir.Function(module, strlen_s, '.object.str.__len__'))
    strlen.attributes.add('nonlazybind')
    strlen.linkage='private'
    irbuilder = ir.IRBuilder(strlen.append_basic_block('entry'))

    # extract element 0, the length

    s1 = strlen.args[0]
    s2 = irbuilder.gep(s1,
        [ir.Constant(ir.IntType(32), 0),
        ir.Constant(ir.IntType(32), 0),]
    )
    s3 = irbuilder.load(s2)

    irbuilder.ret(s3)

    # type builders:
    # int() to: str(), float()
    # str() to: int(), float()
    # float() to: int(), str()
    # number-to-number conversions should be codegenned as a cast
    # eventually create a grid

    '''
    One of the problems we have now:
    how do we deal with the stuff that's codegenned in advance, programmatically,
    vs. the stuff we have to codegen by way of library functions?
    what prevents us from doing everything as library functions?
    we need to find out what those things are.
    barring that, we need a way to more efficiently generate programmatic functions
    that we could also use to produce the casts between types we need here
    '''
    
    # for n in VarTypes:
    #     if isinstance(VarTypes[n], ir.types.IntType):
        
    # mkstr_s = ir.FunctionType(VarTypes.i32, [VarTpes.str.as_pointer()])
    # mkstr = mangle_function(ir.Function(module, mkstr_s, '.i32.__str__'))

    # mkstr.attributes.add('nonlazybind')
    # mkstr.linkage='private'
    # irbuilder = ir.IRBuilder(mkstr.append_basic_block('entry'))

    # construct a call to snprintf
    # get syntax for that
    # and print into the buffer
    # then construct the new object

    # each int type should be converted to either signed or unsighned i64 first,
    # and then we call based on that?
