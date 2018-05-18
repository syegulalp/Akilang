def stdlib(self, module):

    # TODO: emit all this as bitcode

    import llvmlite.ir as ir
    
    from aki.vartypes import VarTypes
    from aki.mangling import mangle_function

    # PLATFORM CONSTANTS

    # Add cr/lf constant (for win32 use only)

    _crlf = '\r\n'

    _type = ir.ArrayType(VarTypes.byte, len(_crlf))

    const = ir.GlobalVariable(module, _type, '.const.crlf')
    const.global_constant = True
    const.storage_class = 'private'
    const.align = 8
    const.initializer = ir.Constant(_type, bytearray(_crlf.encode()))

    # Add atoi
    # TODO:untested

    atoi_s = ir.FunctionType(VarTypes.i32, [VarTypes.str.ext_ptr])
    atoi_f = ir.Function(module, atoi_s, 'atoi')
    atoi_f._local_visibility = False
    atoi_f.args[0]._name = "s"

    # print for win32
    # TODO: to be replaced with a call to plain old snprintf

    llvm_stdout_s = ir.FunctionType(VarTypes.i64, [VarTypes.i32])
    llvm_stdout = ir.Function(module, llvm_stdout_s, 'GetStdHandle')
    llvm_stdout._local_visibility = False

    llvm_writefile_s = ir.FunctionType(VarTypes.i32, [
        VarTypes.i64,
        VarTypes.i8.as_pointer(), VarTypes.i32,
        VarTypes.i32.as_pointer(),
        VarTypes.i8.as_pointer()
    ])

    llvm_writefile = ir.Function(module, llvm_writefile_s, 'WriteFile')
    llvm_writefile._local_visibility = False

    # c_data for string

    cdata_s = ir.FunctionType(VarTypes.i8.as_pointer(),
                              [VarTypes.str.as_pointer()])
    cdata = mangle_function(ir.Function(module, cdata_s, "c_data"))
    cdata.linkage='private'
    cdata.args[0]._name = "s"

    irbuilder = ir.IRBuilder(cdata.append_basic_block('entry'))
    data_ptr = irbuilder.gep(cdata.args[0], [
        ir.Constant(ir.IntType(32), 0),
        ir.Constant(ir.IntType(32), 0),
    ], True, 's1')
    strptr = irbuilder.load(data_ptr, 's2')
    irbuilder.ret(strptr)

    # strcmp and string equality
    # TODO:untested
    # I think this could be moved to lib now that we have c_data

    # strcmp_s = ir.FunctionType(VarTypes.i32, [VarTypes.i8.as_pointer(), VarTypes.i8.as_pointer()])
    # strcmp = ir.Function(module,strcmp_s,'strcmp')
    # strcmp._local_visibility = False

    # stringeq_s = ir.FunctionType(VarTypes.i32, [VarTypes.str.as_pointer(), VarTypes.str.as_pointer()])
    # stringeq = mangle_function(ir.Function(module, stringeq_s, '.object.str.__eq__'))
    # stringeq._local_visibility = False
    # irbuilder = ir.IRBuilder(stringeq.append_basic_block('entry'))

    # s=[]
    # for x,n in enumerate(stringeq.args):
    #     n.name=f's{x+1}'
    #     _str=irbuilder.gep(n, [
    #         ir.Constant(ir.IntType(32),0),
    #         ir.Constant(ir.IntType(32),0),
    #         ], True, f'str{x}')
    #     s.append(irbuilder.load(_str))

    # s2 = irbuilder.call(strcmp,s)
    # irbuilder.ret(s2)
