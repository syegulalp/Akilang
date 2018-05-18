from llvmlite.ir.types import PointerType, Type
import llvmlite.ir as ir


class MyType():
    pointee = None
    v_id = None

    def is_obj_ptr(self):
        try:
            is_obj = self.pointee.is_obj
        except:
            is_obj = False
        return is_obj

    def is_original_obj(self):
        try:
            is_original_obj = self.pointee.original_obj
        except:
            is_original_obj = None
        return is_original_obj

    def descr(self):
        if self.is_obj_ptr():
            return self.pointee.v_id.replace('_', ' ')
        return self.v_id.replace('_', ' ')


# now, how to use this to patch v_id behaviors globally?
# for now I'm OK with using underscores
# getter/setter behavior on descr would probably help

ir.types.Type.descr = MyType.descr
ir.types.Type.is_obj_ptr = MyType.is_obj_ptr
ir.types.Type.is_original_obj = MyType.is_original_obj


class _PointerType(PointerType):
    def __init__(self, *a, **ka):
        v_id = ka.pop('v_id', '')
        signed = ka.pop('signed', '')
        super().__init__(*a, **ka)
        self.v_id = "ptr_" + v_id
        self.signed = signed

    def as_pointer(self, addrspace=0):
        return _PointerType(
            self, addrspace, v_id=self.v_id, signed=self.signed)


class _IntType(ir.types.Type):
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
        self = super(_IntType, cls).__new__(cls)
        self.width = bits
        self.signed = signed
        if v_id is not None:
            self.v_id = v_id
        else:
            self.v_id = f'{"i" if self.signed else "u"}{self.width}'
        return self

    def as_pointer(self, addrspace=0):
        return _PointerType(self, addrspace, v_id=self.v_id)

    # Everything after this is a copy of the original IntType

    def __getnewargs__(self):
        return self.width,

    def __copy__(self):
        return self

    def _to_string(self):
        return f'i{self.width}'

    def __eq__(self, other):
        if isinstance(other, _IntType):
            return self.width == other.width
        else:
            return False

    def __hash__(self):
        return hash(_IntType)

    def format_constant(self, val):
        if isinstance(val, bool):
            return str(val).lower()
        else:
            return str(val)

    @property
    def intrinsic_name(self):
        return str(self)


ir.types.IntType = _IntType
ir.IntType = _IntType


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