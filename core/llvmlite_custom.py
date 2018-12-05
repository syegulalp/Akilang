import llvmlite.ir as ir

import ctypes

_Type = ir.types.Type

class MyType():
    
    def is_func_ptr(self):
        '''
        Reports whether or not a given type
        is a function pointer.
        '''
        try:
            is_func = isinstance(
                self.pointee.pointee,
                ir.FunctionType
            )
        except:
            return False
        else:
            return is_func

    def is_obj_ptr(self):
        '''
        Reports whether or not a given type
        points directly to an object.
        '''

        try:
            return self.pointee.is_obj
        except AttributeError:
            return False

    def describe(self):
        return self.v_id

    def signature(self):
        if not self.is_obj:
            raise Exception("Not an object")
        return f'.object.{self.v_id}.'

    def del_signature(self):
        _del = '__del__'
        if hasattr(self, 'del_id'):
            sig = f'.object.{self.del_id}.{_del}'
        else:
            sig = f'{self.signature()}{_del}'
        return sig

    def new_signature(self):
        _new = '__new__'
        if self.is_obj_ptr():
            v = f'.object.{self.pointee.v_id}.{_new}'
        else:
            v = f'.{self.v_id}.{_new}'
        return v

for k,v in MyType.__dict__.items():
    if not k.startswith('__'):
        setattr(_Type,k,v)

_Type.is_obj = None
_Type.v_id = None
_Type.del_as_ptr = False

_Type.post_new_bitcast = lambda *a, **ka: None


class _PointerType(ir.types.PointerType):
    def __init__(self, *a, **ka):
        v_id = ka.pop('v_id', '')
        signed = ka.pop('signed', '')
        super().__init__(*a, **ka)
        self.v_id = "ptr_" + v_id
        self.signed = signed
        self.descr = lambda: "ptr " + v_id
        self.p_fmt = getattr(a[0], 'p_fmt', None)
        self.c_type = ctypes.c_void_p

    def as_pointer(self, addrspace=0):
        return _PointerType(
            self, addrspace, v_id=self.v_id, signed=self.signed)


ir.types.PointerType = _PointerType

Old_IntType = ir.types.IntType

class _IntType(Old_IntType):
    """
    The type for integers.
    """
    null = '0'
    _instance_cache = {}

    def __new__(cls, bits, force=False, signed=True, v_id=None):
        signature = (bits, signed, v_id)
        if force:
            return cls.__new(*signature)
        # Cache all common integer types
        if 0 <= bits <= 128:
            try:
                return cls._instance_cache[signature]
            except KeyError:
                inst = cls._instance_cache[signature] = cls.__new(*signature)
                return inst
        return cls.__new(*signature)

    @classmethod
    def __new(cls, bits, signed, v_id):
        assert isinstance(bits, int) and bits >= 0
        self = super(Old_IntType, cls).__new__(cls)  # pylint: disable=E1003
        self.width = bits
        self.signed = signed
        if v_id is not None:
            self.v_id = v_id
        else:
            self.v_id = f'{"i" if self.signed else "u"}{self.width}'
        return self

    def as_pointer(self, addrspace=0):
        return _PointerType(self, addrspace, v_id=self.v_id)


ir.types.IntType = _IntType
ir.IntType = _IntType

old_NamedValue_init = ir.values.NamedValue.__init__


def NamedValue_init(self, parent, type, name):
    old_NamedValue_init(self, parent, type, name)
    self.heap_alloc = False
    self.tracked = False
    self.do_not_allocate = False
    self.input_arg = None


ir.values.NamedValue.__init__ = NamedValue_init

old_Constant_init = ir.values.Constant.__init__


def Constant_init(self, typ, constant):
    old_Constant_init(self, typ, constant)
    self.heap_alloc = False
    self.tracked = False
    self.do_not_allocate = False
    self.input_arg = None


ir.values.Constant.__init__ = Constant_init

OldInit = ir.Function.__init__


def __init(self, *a, **ka):
    OldInit(self, *a, **ka)
    self.decorators = []
    self.raises_exception = False


ir.Function.__init__ = __init

