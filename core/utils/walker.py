from core.parsing import Parser

class Function():
    def __init__(self):
        self.variables = {}

class Walker():
    def __init__(self, code):
        self.walker = Parser().parse_generator(code)
        self.functions = {}

    def walk(self, walker=None):
        if walker is None:
            walker = self.walker
        for node in walker:
            method = f'_walk_{node.__class__.__name__}'
            result = getattr(self, method)(node)            
            return result

    def _walk_Function(self, node):
        self.functions[node.proto.name] = Function()
        return self.walk(node.body.expr_list)

    def _walk_Var(self, node):
        # these are variable declarations
        return self.walk(node.vars)
    
    def _walk_Call(self, node):
        pass

    def _walk_Number(self, node):
        pass

    def _walk_Variable(self, node):
        return node.name

if __name__ == '__main__':

    code = '''
    def main(){
        var x:i32=32
        print (x)
        0
    }
    def main2(){
        0
    }
    '''

    w= Walker(code)
    w.walk()
    print (w.functions)

# find out whether or not a given variable is ever given away
# if so, is it given away to a @nomod function?
# is it returned from a @nomod function? (as a call result)
# if its owner remains consistent, then we heap allocate
# if not, we stack allocate 