import llvmlite.ir as ir

from core.vartypes import VarTypes
from core.stdlib import makecall, makefunc

def platform_lib(self, module):

    # Eventually this will be written out to bitcode
    # and cached on disk

    n = r'''
# Microsoft Win32/NT library interfaces

extern SetConsoleOutputCP(codepage :u32) :bool
extern GetConsoleOutputCP() :u32

extern MultiByteToWideChar(
    CodePage: u32, dwFlags: u32, 
    lpMultiByteStr:ptr u8,
    cbMultiByte: i32,
    lpWideCharStr: ptr u8,
    cchWideChar: i32
)

extern printf(str_fmt :ptr i8, *va) :i32
extern _snprintf(str_buf: ptr u_mem, str_size:u_size, str_fmt: ptr i8, *va): i32
extern strlen(str_to_check: ptr u_mem): u_size

extern rand():i32

extern GetProcessHeap():u_size
extern HeapAlloc(handle:u_size, flags:u32, bytes:u_size):ptr u_mem
extern HeapFree(handle:u_size, flags:u32, m:ptr u_mem): bool

extern memcpy_s(dest:ptr u_size, size:u_size, source: ptr u_mem, count: u_size)

extern _getwch():i32
extern gets_s(input:ptr u_mem, bytes:u_size)
extern atoi(string: ptr u_mem): i32

extern _get_errno(errno:ptr i32) :i32

extern memset(item:ptr u_mem, v:u8, size:u64)

@inline
def c_strlen(str_to_check: ptr u_mem): u_size
    strlen(str_to_check)

@inline
def c_alloc(bytes:u_size):ptr u_mem
    HeapAlloc(GetProcessHeap(), 8u, bytes)

@inline
def c_alloc(bytes:i32):ptr u_mem
    c_alloc(cast(bytes, u_size))

@inline
@unsafe_req
def c_free(m:ptr u_mem):bool {
    var free_call = HeapFree(GetProcessHeap(), 0u, m)
    var result = (free_call !=0b)
    when result then memset(m, 0B, c_size(m))    
    result
}

@inline
def set_codepage(codepage :u32) :bool
    SetConsoleOutputCP(codepage)

@inline
def get_codepage() :u32
    GetConsoleOutputCP()

def int_to_c_str(my_int:i32): ptr u_mem {
    var size = c_size(my_int) * 4U + 1U
    var buffer = c_alloc(size)
    _snprintf(buffer, size, c_data('%i'),my_int)
    return buffer
}

@nomod
def c_str_to_int(my_str:str) :i32 {
    atoi(c_data(my_str))
}

def '.object.str.__len__'(my_str:str):u64{
    var f1=unsafe c_ptr(my_str, u_size)
    c_deref(f1)
}

# TODO: untested
def '.object.array.__del__'(my_obj:ptr u_mem):bool {
    unsafe c_free(my_obj)
}

# TODO: untested
def '.object.str.__del__'(my_obj: ptr u_mem):bool {
    unsafe c_free(my_obj)
}

# TODO: untested
def '.object.str.__new__'(my_obj:ptr u_mem):str {
    # Determine the string length since this is raw data
    var str_len = c_strlen(my_obj)
    
    # Allocate an object of the correct size and type
    var alloc = c_obj_alloc(with var x:str{x})

    # Insert the length
    var len_ptr = c_gep(alloc,0)
    unsafe c_ptr_mod(len_ptr, str_len)

    # Point to the data
    var data_ptr = c_gep(alloc,1)    
    unsafe c_ptr_mod(data_ptr, my_obj)
    
    # Return the string object
    return alloc
}

    '''

    for _ in self.eval_generator(n):
        pass

    # This is all the instructions that have to come AFTER
    # the platform libraries are loaded
    # for instance, because we don't know how malloc or free work

    #
    # len for string object
    #

    # strlen, irbuilder = makefunc(
    #     module,
    #     '.object.str.__len__',
    #     VarTypes.u64, [VarTypes.str.as_pointer()]
    # )

    # s1 = strlen.args[0]
    # s2 = irbuilder.gep(
    #     s1,
    #     [self.codegen._i32(0),
    #      self.codegen._i32(0), ]
    # )
    # s3 = irbuilder.load(s2)

    # irbuilder.ret(s3)

    # del for array:

    # obj_del, irbuilder = makefunc(
    #     module,
    #     '.object.array.__del__', VarTypes.bool,
    #     [VarTypes.u_mem.as_pointer()]
    # )

    # result = makecall(
    #     irbuilder, module,
    #     'c_free',
    #     [
    #         obj_del.args[0]
    #     ]
    # )

    # irbuilder.ret(result)


    #
    # del for string
    #

    # obj_del, irbuilder = makefunc(
    #     module,
    #     '.object.str.__del__', VarTypes.bool,
    #     [VarTypes.u_mem.as_pointer()],
    #     no_mangle = True
    # )

    # # this just deletes the string object,
    # # not the string data (for now)

    # # ptr_cast = irbuilder.bitcast(
    # #     obj_del.args[0],
    # #     VarTypes.u_mem.as_pointer()
    # # )

    # # # is there any way to determine at compile time
    # # # whether or not we need to delete the underlying data?

    # # #data_ptr = 

    # result = makecall(
    #     irbuilder, module,
    #     'c_free',
    #     [obj_del.args[0],]
    # )

    # irbuilder.ret(result)

    #
    # new string from raw pointer:
    #

    str_fn, irbuilder = makefunc(
        module,
        '.object.xstr.__new__', VarTypes.str.as_pointer(),
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

    n = r'''

def utf_to_wide(in_str:str):ptr u8 {
  
    # TODO: untracked, b/c raw c_alloc calls
    # don't flag for tracking

    # TODO: a good test case for auto-promotion
    # of ints?

    var str_len = len(in_str)
    var out_size = str_len*2U

    var out_data=c_alloc(out_size)

    MultiByteToWideChar(
        65001u, 0, 
        c_data(in_str),
        cast(str_len,i32),
        out_data,
        cast(out_size,i32)
    )

    return out_data
}

# general cross-platform functions

def inkey():i32 {
    var key:i32
    key=_getwch()
    if (key==0 or key==224) then key=_getwch()
    return key
}

def input(bufsize:i32=1024):str{
    var buf=c_alloc(bufsize)
    var err:i32
    
    gets_s(
        buf, cast(bufsize,u64)
    )
    
    # we don't do anything with this yet,
    # but in time we will
    _get_errno(c_ref(err))

    var s_len = strlen(buf)-1U
    
    var cr=c_ptr_math(
        buf, s_len
    )

    # NT compatibility - strip CRs
    if (c_deref(cr) == 13B) then
        unsafe {
        c_ptr_mod(cr, 0B)
    }

    return str(buf)   
}

'''    

    for _ in self.eval_generator(n):
        pass