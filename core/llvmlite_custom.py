from llvmlite.ir.types import PointerType, Type
import llvmlite.ir as ir

class MyType():
    pointee = None
    v_id = None

    def is_func(self):
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

ir.types.Type.describe = MyType.describe
ir.types.Type.is_obj_ptr = MyType.is_obj_ptr
ir.types.Type.is_func = MyType.is_func
ir.types.Type.signature = MyType.signature

class _PointerType(PointerType):
    def __init__(self, *a, **ka):
        v_id = ka.pop('v_id', '')
        signed = ka.pop('signed', '')
        super().__init__(*a, **ka)
        self.v_id = "ptr_" + v_id
        self.signed = signed
        self.descr = lambda: "ptr " + v_id

    def as_pointer(self, addrspace=0):
        return _PointerType(
            self, addrspace, v_id=self.v_id, signed=self.signed)

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
        self = super(Old_IntType, cls).__new__(cls)
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
    self.do_not_allocate = False
    self.input_arg = None

ir.values.NamedValue.__init__ = NamedValue_init

old_Constant_init = ir.values.Constant.__init__

def Constant_init(self, typ, constant):
    old_Constant_init(self,typ,constant)
    self.heap_alloc = False
    self.do_not_allocate = False
    self.input_arg = None

ir.values.Constant.__init__ = Constant_init


class Map(dict):
    # https://stackoverflow.com/a/32107024
    def __init__(self, *args, **kwargs):
        super(Map, self).__init__(*args, **kwargs)
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v

        if kwargs:
            for k, v in kwargs.items():
                self[k] = v

    def __getattr__(self, attr):
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(Map, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(Map, self).__delitem__(key)
        del self.__dict__[key]