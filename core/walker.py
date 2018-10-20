from core.parsing import Parser


class Walker():
    def __init__(self, code):
        self.walker = Parser().parse_generator(code)

    def walk(self):
        for node in self.walker:
            method = f'_walk_{node.__class__.__name__}'
            result = getattr(self, method)(node)
            print(result)

    def _walk_Function(self, node):
        for statement in node.body.expr_list:
            print(statement.__class__)


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

    Walker(code).walk()
