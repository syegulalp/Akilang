from llvmlite import ir
from core.akitypes import (
    AkiType,
    AkiBool,
    AkiFunction,
    AkiObject,
    AkiTypeMgr,
    AkiPointer,
)

from core.astree import (
    VarTypeNode,
    VarTypeName,
    VarTypeFunc,
    VarTypePtr,
    BinOpComparison,
    Constant,
    IfExpr,
    Name,
    VarList,
    Assignment,
    WithExpr,
    Prototype,
    LLVMNode,
    Argument,
    Function,
    ExpressionBlock,
    External,
)
from core.error import (
    AkiNameErr,
    AkiTypeErr,
    AkiOpError,
    AkiBaseErr,
    AkiSyntaxErr,
    LocalException,
)
from core.repl import CMD, REP
from typing import Optional


class FuncState:
    """
    Object for storing function state, such as its symbol table,
    and context information such as the decorator stack and 
    `unsafe` states.
    TODO: let's make this into a context manager, maybe
    """

    def __init__(self):

        # Function currently in context.
        self.fn = None
        self.return_value = None

        # Breakpoint stack for function.
        self.breakpoints = []

        # Symbol table for function.
        self.symtab = {}


class AkiCodeGen:
    """
    Code generation module for Akilang.
    """

    def __init__(
        self,
        module: Optional[ir.Module] = None,
        typemgr=None,
        module_name: Optional[str] = None,
    ):

        # Create an LLVM module if we aren't passed one.

        if module is None:
            self.module = ir.Module(name=module_name)
        else:
            self.module = module

        self.fn: Optional[FuncState] = None
        self.text: Optional[str] = None

        # Create a type manager module if we aren't passed one.

        if typemgr is None:
            self.typemgr = AkiTypeMgr(module=self.module)
            self.types = self.typemgr.types
        else:
            self.typemgr = typemgr
            self.types = typemgr.types

        # Other codegen modules to check for namespaces.
        # Resolved top to bottom.
        self.other_modules: list = []

        self.const_enum = 0

    def _const_counter(self):
        self.const_enum += 1
        return self.const_enum

    def init_func_handlers(self):
        """
        Called when we create a new function.
        This sets up the state of the function,
        as used elsewhere throughout the module.
        """

        self.builder = None
        self.fn = FuncState()

    def eval(self, ast):
        """
        Evaluates an AST expression tree beginning with a top-level node.
        """

        for _ in ast:
            self._codegen(_)

    def _codegen(self, node):
        """
        Dispatch function for codegen based on AST classes.
        """
        method = f"_codegen_{node.__class__.__name__}"
        result = getattr(self, method)(node)
        return result

    def _codegen_LLVMNode(self, node):
        return node.llvm_node

    def _name(self, node, name_to_find, other_module=None):
        """
        Retrieve a name reference, not the underlying value,
        from the symbol table or the list of globals.
        """

        # First, look in the function symbol table:
        name = self.fn.symtab.get(name_to_find, None)

        if name is not None:
            return name

        # Next, look in the globals:
        name = self.module.globals.get(name_to_find, None)

        if name is not None:
            return name

        # Next, look in other modules:
        for _ in self.other_modules:
            name = _.module.globals.get(name_to_find, None)
            if name is not None:
                # emit function reference for this module
                link = ir.Function(self.module, name.ftype, name.name)
                # copy aki data for function
                link.akinode = name.akinode
                link.akitype = name.akitype
                for n_arg, l_arg in zip(name.args, link.args):
                    l_arg.akinode = n_arg.akinode
                return name

        if name is None:
            raise AkiNameErr(
                node, self.text, f'Name "{CMD}{name_to_find}{REP}" not found'
            )

    def _alloca(self, node, llvm_type, name, size=None, is_global=False):
        """
        Allocate space for a variable.
        Right now this is stack-only; eventually it'll include
        heap allocations, too.
        """

        return self.builder.alloca(llvm_type, size, name)

    def _delete_var(self, name):
        """
        Deletes a variable from the local scope.
        Eventually this will be where we make decisions about
        deallocating heap-allocated objects when they
        pass out of scope, etc.
        """

        del self.fn.symtab[name]

    #################################################################
    # Type AST node walker
    #################################################################

    def _get_vartype(self, node: VarTypeNode):
        """
        Looks up a type in the current module
        based on a `VarType` AST node sequence.
        """
        if isinstance(node, AkiType):
            return node
        return getattr(self, f"_get_vartype_{node.__class__.__name__}")(node)

    def _get_vartype_VarTypeName(self, node):
        """
        Node visitor for `VarTypeName` nodes.
        """
        if node.name is None:
            id_to_get = self.typemgr._default.type_id
        else:
            id_to_get = node.name

        var_lookup = self._get_type_by_name(id_to_get)
        if var_lookup is None:
            raise AkiTypeErr(
                node, self.text, f'Unrecognized type definition "{CMD}{id_to_get}{REP}"'
            )

        return var_lookup

    def _get_vartype_VarTypePtr(self, node):
        """
        Node visitor for `VarTypePtr` nodes.
        """
        aki_type = self._get_vartype(node.pointee)
        aki_type = self.typemgr.as_ptr(aki_type, literal_ptr=True)
        return aki_type

    def _get_vartype_VarTypeFunc(self, node):
        """
        Node visitor for `VarTypeFunc` nodes.
        """
        for _ in node.arguments:
            _.akitype = self._get_vartype(_)
            _.llvm_type = _.akitype.llvm_type

        node.return_type.akitype = self._get_vartype(node.return_type)

        aki_node = AkiFunction(node.arguments, node.return_type.akitype)
        node.name = aki_node.type_id

        return aki_node

    def _get_type_by_name(self, type_name):
        """
        Find a type in the current module by name.
        Does not distinguish between built-in types and
        types registered with the module, e.g., by function signatures.
        """
        type_to_find = self.types.get(type_name, None)
        if type_to_find is None:
            return None
        if isinstance(type_to_find, AkiType):
            return type_to_find
        return None

    #################################################################
    # Utilities
    #################################################################

    def _move_before_terminator(self, block):
        """
        Position in an existing LLVM block before the terminator instruction.
        """
        assert block.is_terminal
        self.builder.position_before(block.instructions[-1])

    def _check_var_name(self, node, name, is_global=False):
        """
        Check routine to determine if a given name is already in use
        in a given context.
        """
        context = self.module.globals if is_global else self.fn.symtab
        if name in context:
            raise AkiNameErr(
                node, self.text, f'Name "{CMD}{name}{REP}" already used in this context'
            )

    def _scalar_as_bool(self, node, expr):
        """
        Takes an LLVM instruction result of a scalar type
        and converts it to a boolean type.
        """
        result = self._codegen(
            BinOpComparison(
                node,
                "!=",
                LLVMNode(node, expr.akitype, expr),
                Constant(node, expr.akitype.default(), expr.akitype),
            )
        )
        return result

    def _is_type(self, node, expr, other_type):
        akitype = getattr(expr, "akitype", None)
        if not akitype:
            raise AkiSyntaxErr(node, self.text, f"Expression does not yield a value")
        return isinstance(akitype, other_type)

    def _type_check_op(self, node, lhs, rhs):
        """
        Perform a type compatibility check for a binary op.
        This takes in two LLVM nodes decorated with Aki data.
        """

        self._is_type(node.lhs, lhs, AkiType)
        lhs_atype = lhs.akitype

        self._is_type(node.rhs, rhs, AkiType)
        rhs_atype = rhs.akitype

        if lhs_atype != rhs_atype:

            error = f'"{CMD}{lhs.akinode.name}{REP}" ({CMD}{lhs_atype}{REP}) and "{CMD}{rhs.akinode.name}{REP}" ({CMD}{rhs_atype}{REP}) do not have compatible types for operation "{CMD}{node.op}{REP}"'

            if lhs_atype.signed != rhs_atype.signed:
                is_signed = lambda x: "Signed" if x else "Unsigned"
                error += f'\nTypes also have signed/unsigned disagreement:\n - "{CMD}{lhs.akinode.name}{REP}" ({CMD}{lhs_atype}{REP}): {is_signed(lhs_atype.signed)}\n - "{CMD}{rhs.akinode.name}{REP}" ({CMD}{rhs_atype}{REP}): {is_signed(rhs_atype.signed)}'

            raise AkiTypeErr(node, self.text, error)
        return lhs_atype, rhs_atype

    #################################################################
    # Top-level statements
    #################################################################

    def _codegen_Prototype(self, node):
        """
        Generate a function prototype for the LLVM module
        from the `Prototype` AST node.
        """
        # Name collision check

        self._check_var_name(node, node.name, True)

        # Generate function arguments.
        # Add LLVM type information to each argument,
        # based on the type information available in the node.

        func_args = []

        require_defaults = False

        # Node.arguments are Aki type nodes

        for _ in node.arguments:
            if _.default_value is not None:
                require_defaults = True
                if isinstance(_.default_value, ExpressionBlock):
                    raise AkiSyntaxErr(
                        _.default_value,
                        self.text,
                        f"Function argument defaults cannot be an expression block (yet)",
                    )

            if not _.default_value and require_defaults:
                raise AkiSyntaxErr(
                    _,
                    self.text,
                    f'Function "{node.name}" has non-default argument "{_.name}" after default arguments',
                )
            if _.vartype.name is None:
                _.vartype.name = self.typemgr._default.type_id
            arg_vartype = self._get_vartype(_.vartype)

            _.vartype.llvm_type = arg_vartype.llvm_type
            _.vartype.akitype = arg_vartype

            # The func_args supplied to the f_type call
            # are standard LLVM types
            func_args.append(arg_vartype.llvm_type)

        # Set return type.
        return_type = self._get_vartype(node.return_type)
        node.return_type.akitype = return_type

        # This is for the sake of compatibility with
        # things that expect a `vartype`
        node.vartype = node.return_type

        # Generate function prototype.

        f_type = ir.FunctionType(return_type.llvm_type, func_args)
        f_type.return_type.akitype = return_type

        for p_arg, n_arg in zip(f_type.args, node.arguments):
            p_arg.akinode = n_arg

        proto = ir.Function(self.module, f_type, name=node.name)

        proto.calling_convention = "fastcc"

        # Set variable types for function

        function_type = AkiFunction([_.vartype for _ in node.arguments], return_type)

        proto.akinode = node
        proto.akitype = function_type

        # Add the function signature to the list of types for the module,
        # using the function's name

        _ = self.typemgr.add_type(node.name, function_type, self.module)
        if _ is None:
            raise AkiTypeErr(node, self.text, "Invalid name")
        proto.enum_id = proto.akitype.enum_id

        # Add Aki type metadata
        # TODO:
        # store the original string for the function sig and use that

        # aki_type_metadata = self.module.add_metadata([str(proto.akitype)])
        # proto.set_metadata("aki.type", aki_type_metadata)

        return proto

    def _codegen_External(self, node):
        """
        Generate an external function call from an `External` AST node.
        """

        return self._codegen_Function(node)

    def _codegen_Function(self, node):
        """
        Generate an LLVM function from a `Function` AST node.
        """

        self.init_func_handlers()

        # Generate function prototype.
        func = self._codegen(node.prototype)

        # Store an original function reference in the prototype.
        # This is so we can refer to it later if we use
        # a function pointer.
        func.akitype.original_function = func

        self.fn.fn = func

        if isinstance(node, External):
            for a, b in zip(func.args, node.prototype.arguments):
                # make sure the variable name is not in use
                self._check_var_name(b, b.name)
                # set its Aki attributes
                # var_alloc.akitype = b.vartype.akitype
                # var_alloc.akinode = b
                # set the akinode attribute for the original argument,
                # so it can be referenced if we need to throw an error
                a.akitype = b.vartype.akitype
                a.akinode = b
            return func

        # Generate entry block and function body.

        self.entry_block = func.append_basic_block("entry")
        self.builder = ir.IRBuilder(self.entry_block)

        # Add prototype arguments to function symbol table
        # and add references in function.
        # Use isinstance(ir.Argument) to determine if the
        # var being looked up is a func arg.

        for a, b in zip(func.args, node.prototype.arguments):
            # make sure the variable name is not in use
            self._check_var_name(b, b.name)
            # create an allocation for the variable
            var_alloc = self._alloca(b, b.vartype.llvm_type, b.name)
            # set its Aki attributes
            var_alloc.akitype = b.vartype.akitype
            var_alloc.akinode = b
            # set the akinode attribute for the original argument,
            # so it can be referenced if we need to throw an error
            a.akinode = b
            # add the variable to the symbol table
            self.fn.symtab[b.name] = var_alloc
            # store the default value to the variable
            self.builder.store(a, var_alloc)

        # Add return value holder.

        self.fn.return_value = self._alloca(
            node, func.return_value.type, ".function_return_value"
        )

        # Set Akitype values for the return value holder
        # and for the function's actual return value.

        self.fn.return_value.akitype = func.akitype.return_type
        func.return_value.akitype = func.akitype.return_type

        # Create actual starting function block and codegen instructions.

        self.body_block = func.append_basic_block("body")
        self.builder.branch(self.body_block)
        self.builder.position_at_start(self.body_block)

        result = self._codegen(node.body)

        # If we have an empty function body,
        # load the default value for the return type
        # and return that.

        assert isinstance(result, ir.Instruction)

        # TODO: We need to set a flag somewhere indicating that the function
        # did not return a value, so that it can be used later.
        # (for instance, when checking to see if a given statement returns a value)
        # This could be set in the LLVM function object,
        # in the Aki type for the function definition,
        # or in the AST node. Not sure which one would be best.

        if result is None:
            result = self._codegen(
                Constant(
                    node.body.p,
                    node.prototype.return_type.akitype.default(),
                    node.prototype.return_type,
                )
            )

        # If we don't explicitly assign a return type on the function prototype,
        # we infer it from the return value of the body.

        if node.prototype.return_type.name is None:

            # Set the result holder
            r_type = result.akitype

            self.fn.return_value.type = r_type.llvm_type.as_pointer()
            self.fn.return_value.akitype = r_type

            # Set the actual type for the function
            func.return_value = r_type.llvm_type

            # Set the return value type as used by the REPL
            func.return_value.akitype = r_type

        # If the function prototype and return type still don't agree,
        # throw an exception

        if result.akitype != self.fn.return_value.akitype:
            raise AkiTypeErr(
                node,
                self.text,
                f'Return value from function "{CMD}{func.name}{REP}" ({CMD}{result.akitype}{REP}) does not match function signature return type ({CMD}{self.fn.return_value.akitype}{REP})',
            )

        # Add return value for function in exit block.

        self.builder.store(result, self.fn.return_value)

        # branch to exit, return the return value.

        exit_block = func.append_basic_block("exit")
        self.builder.branch(exit_block)

        self.builder.position_at_start(exit_block)
        self.builder.ret(self.builder.load(self.fn.return_value, ".ret"))

        # Reset function state handlers.

        self.fn = None

        return func

    #################################################################
    # Blocks
    #################################################################

    def _codegen_ExpressionBlock(self, node):
        """
        Codegen each expression in an `Expression` Block.
        """
        result = None
        for _ in node.body:
            result = self._codegen(_)
        return result

    #################################################################
    # Declarations
    #################################################################

    def _codegen_VarList(self, node):
        """
        Codegen the variables in a `VarList` node.
        """
        for _ in node.vars:

            self._check_var_name(_, _.name)

            # Create defaults if no value or vartype

            # If no value ...

            value = None

            if _.val is None:

                # and no default vartype, then create the default

                if _.vartype is None:
                    _.vartype = Name(_.p, self.type.default.type_id)

                _.akitype = self._get_vartype(_.vartype)
                _.val = Constant(_.p, _.akitype.default(), _.vartype)
                value = _.val

            else:

                # If there is a value ...

                value = self._codegen(_.val)

                # and there is no type identifier on the variable ...

                if _.vartype.name is None:
                    # then use the value's variable type
                    _.vartype = value.akinode.vartype
                    _.akitype = value.akitype
                else:
                    # otherwise, use the named vartype
                    _.akitype = self._get_vartype(_.vartype)

                value = LLVMNode(_.val, _.vartype, value)

            # Create an allocation for that type
            var_ptr = self._alloca(_, _.akitype.llvm_type, _.name)

            # Store its node attributes
            var_ptr.akitype = _.akitype
            var_ptr.akinode = _

            # Store the variable in the function symbol table
            self.fn.symtab[_.name] = var_ptr

            # and store the value itself to the variable
            # by way of an Assignment op
            self._codegen(Assignment(_.p, "=", Name(_.p, _.name), value))

    #################################################################
    # Control flow
    #################################################################

    def _codegen_Call(self, node):
        """
        Generate a function call from a `Call` node.
        """

        # check if this is a builtin

        builtin = getattr(self, f"_builtins_{node.name}", None)
        if builtin:
            return builtin(node)

        # check if this is a request for a type
        # this will eventually go somewhere else

        try:

            named_type = self._get_type_by_name(node.name)

            if named_type is not None and not isinstance(named_type, AkiFunction):

                if len(node.arguments) != 1:

                    # Create a fake function definition to handle the error

                    call_func = self._codegen(
                        Function(
                            node,
                            Prototype(
                                node,
                                node.name,
                                [
                                    Argument(
                                        node,
                                        "vartype",
                                        VarTypeName(node, self.types["type"].type_id),
                                    )
                                ],
                                VarTypeName(node, self.types["type"].type_id),
                            ),
                            ExpressionBlock(node, []),
                        )
                    )

                    raise LocalException

                arg = node.arguments[0]

                # this will eventually become a builtin
                if node.name == "type":
                    type_from = self._codegen(arg)
                    const = self._codegen(
                        Constant(arg, type_from.akitype.enum_id, self.types["type"])
                    )
                    return const

                # this will also eventually become a builtin

                if isinstance(arg, Constant):
                    # this check is in place until we have
                    # methods for making ints from floats, etc.
                    if arg.vartype.name != named_type.type_id:
                        raise AkiTypeErr(
                            arg,
                            self.text,
                            f'Constant "{CMD}{arg.val}{REP}" is not type "{CMD}{named_type.type_id}{REP}" (type conversions not yet performed this way)',
                        )

                    const = self._codegen(
                        Constant(arg, arg.val, VarTypeName(arg, named_type.type_id))
                    )
                    return const

                else:
                    raise AkiOpError(
                        node.arguments[0], self.text, f"Only constants allowed for now"
                    )

            call_func = self._name(node, node.name)
            args = []

            # If this is a function pointer, get the original function

            if isinstance(call_func, ir.AllocaInstr):
                cf = call_func.akitype.original_function
                if cf is None:
                    raise AkiTypeErr(
                        node,
                        self.text,
                        f'"{CMD}{node.name}{REP}" is "{CMD}{call_func.akitype}{REP}", not a function',
                    )
                else:
                    call_func = cf

            # If we have too many arguments, give up

            if len(node.arguments) > len(call_func.args):
                raise LocalException

            for _, f_arg in enumerate(call_func.args):

                # If we're out of supplied arguments,
                # see if the function has default args.

                if _ + 1 > len(node.arguments):
                    default_arg_value = f_arg.akinode.default_value
                    if default_arg_value is None:
                        raise LocalException
                    arg_val = self._codegen(default_arg_value)

                    # self._is_type(f_arg.akinode, arg_val, f_arg.akinode.vartype.akitype)

                    args.append(arg_val)
                    continue

                # If we still have supplied arguments,
                # use them instead.

                arg = node.arguments[_]
                arg_val = self._codegen(arg)

                if arg_val.type != call_func.args[_].type:
                    raise AkiTypeErr(
                        arg,
                        self.text,
                        f'Value "{CMD}{arg.name}{REP}" of type "{CMD}{arg_val.akitype}{REP}" does not match {CMD}{node.name}{REP} argument {CMD}{_+1}{REP} of type "{CMD}{call_func.args[_].akinode.vartype.akitype}{REP}"',
                    )

                args.append(arg_val)

        # TODO: list which arguments are optional, along with their defaults

        except LocalException:
            args = "\n".join(
                [
                    f"arg {index+1} = {CMD}{_.name}{_.vartype.akitype}{REP}"
                    for index, _ in enumerate(call_func.akinode.arguments)
                ]
            )
            raise AkiSyntaxErr(
                node,
                self.text,
                f'Function call to "{CMD}{node.name}{REP}" expected {CMD}{len(call_func.args)}{REP} arguments but got {CMD}{len(node.arguments)}{REP}\n{args}',
            )

        call = self.builder.call(call_func, args, call_func.name + ".call")
        call.akitype = call_func.akitype.return_type
        call.akinode = call_func.akinode
        return call

    def _codegen_Break(self, node):
        """
        Codegen a `break` action.
        """

        if not self.fn.breakpoints:
            raise AkiSyntaxErr(
                node, self.text, f'"break" not called within a loop block'
            )

        self.builder.branch(self.fn.breakpoints[-1])

    #################################################################
    # Expressions
    #################################################################

    def _codegen_WithExpr(self, node):
        """
        Codegen a `with` block.
        """

        self._codegen(node.varlist)
        body = self._codegen(node.body)
        for _ in node.varlist.vars:
            self._delete_var(_.name)
        return body

    def _codegen_LoopExpr(self, node):
        """
        Codegen a `loop` expression.
        """

        local_symtab = {}

        # If there are no elements in the loop declaration,
        # assume an infinite loop

        if node.conditions == []:

            start = None
            stop = None
            step = None

        else:

            # Create the loop initialization block

            # TODO:
            # If we only have one element, assume it's the start.
            # If only two, start/stop.
            # If three, start/stop/step.

            if len(node.conditions) != 3:
                raise AkiSyntaxErr(
                    node,
                    self.text,
                    f'"loop" must have three elements (start, stop, step)',
                )

            start = node.conditions[0]
            stop = node.conditions[1]
            step = node.conditions[2]

            loop_init = self.builder.append_basic_block("loop_init")
            self.builder.branch(loop_init)
            self.builder.position_at_start(loop_init)

            # if the first element is a varlist,
            # instantiate each variable in the symbol table,
            # and keep a copy for ourselves so we can
            # delete it later.

            if isinstance(start, VarList):
                self._codegen(start)
                for _ in start.vars:
                    local_symtab[_.name] = self.fn.symtab[_.name]

            # If the first element is just an assignment node,
            # then codegen assignments to the function symbol table.

            elif isinstance(start, Assignment):
                self._codegen(start)

            else:
                raise AkiSyntaxErr(
                    start,
                    self.text,
                    f'"loop" element 1 must be a variable declaration or variable assignment',
                )

        if stop:

            loop_test = self.builder.append_basic_block("loop_test")
            self.builder.branch(loop_test)
            self.builder.position_at_start(loop_test)
            loop_condition = self._codegen(stop)
            with self.builder.if_else(loop_condition) as (then_clause, else_clause):
                with then_clause:
                    loop_body = self._codegen(node.body)
                    n = self._codegen(Assignment(step, "+", step.lhs, step))
                    self.builder.branch(loop_test)
                with else_clause:
                    pass

        else:

            loop = self.builder.append_basic_block("loop_inf")
            loop_exit = self.builder.append_basic_block("loop_exit")
            self.fn.breakpoints.append(loop_exit)
            self.builder.branch(loop)
            self.builder.position_at_start(loop)
            loop_body = self._codegen(node.body)
            self.builder.branch(loop)
            self.builder.position_at_start(loop_exit)
            self.fn.breakpoints.pop()

        # Remove local objects from symbol table

        for _ in local_symtab:
            self._delete_var(_)

        return loop_body

    def _codegen_IfExpr(self, node, is_when_expr=False):
        """
        Codegen an `if` or `when` expression, where then and else return values are of the same type. The `then/else` nodes are raw AST nodes.
        Because the expressions could be indeterminate, we have to codegen them
        to get a vartype.
        """

        if_expr = self._codegen(node.if_expr)

        if not self._is_type(node.if_expr, if_expr, AkiBool):
            if_expr = self._scalar_as_bool(node.if_expr, if_expr)

        if_block = self.builder._block

        # codegen the clauses so we can determine their return types

        with self.builder.if_else(if_expr) as (then_clause, else_clause):
            with then_clause:
                then_block = self.builder._block
                then_result = self._codegen(node.then_expr)
            with else_clause:
                else_block = self.builder._block
                if node.else_expr:
                    else_result = self._codegen(node.else_expr)

        exit_block = self.builder._block

        # for if expresssion, typematch results

        if not is_when_expr:

            if then_result.akitype != else_result.akitype:
                raise AkiTypeErr(
                    node.then_expr,
                    self.text,
                    f'"{CMD}if/else{REP}" must yield same type; use "{CMD}when/else{REP}" for results of different types',
                )

            self._move_before_terminator(if_block)

            if_result = self._alloca(
                node.then_expr, then_result.akitype.llvm_type, ".if_result"
            )

            self._move_before_terminator(then_block)
            self.builder.store(then_result, if_result)

            self._move_before_terminator(else_block)
            self.builder.store(else_result, if_result)

            self.builder.position_at_start(exit_block)
            result = if_result
            result_akitype = then_result.akitype

        # for when expressions, just return the if clause value

        else:

            self._move_before_terminator(if_block)

            if_result = self._alloca(
                node.if_expr, if_expr.akitype.llvm_type, ".when_result"
            )
            self.builder.position_at_start(exit_block)

            result = self.builder.store(if_expr, if_result)
            result_akitype = if_expr.akitype

        result = self.builder.load(if_result)
        result.akitype = result_akitype
        result.akinode = node
        result.akinode.name = f'"if" expr'
        return result

    def _codegen_WhenExpr(self, node):
        """
        Codegen a `when` expression, which returns the value of the `when` itself.
        """
        return self._codegen_IfExpr(node, True)

    #################################################################
    # Operations (also expressions)
    #################################################################

    def _codegen_UnOp(self, node):
        """
        Generate a unary op from an AST `UnOp` node.
        """
        op = self._unops.get(node.op, None)

        if op is None:
            raise AkiOpError(
                node, self.text, f'Operator "{CMD}{node.op}{REP}" not supported'
            )

        operand = self._codegen(node.lhs)
        instr = op(self, node, operand)
        instr.akiype = operand.akitype
        instr.akinode = node
        instr.akinode.name = f'op "{node.op}"'
        return instr

    def _codegen_UnOp_Neg(self, node, operand):
        """
        Generate a unary negation operation for a scalar value.
        """

        op = getattr(operand.akitype, "math_op_negop", None)
        if op is None:
            raise AkiOpError(
                node,
                self.text,
                f'Operator "{CMD}{node.op}{REP}" not supported for type "{CMD}{operand.akitype}{REP}"',
            )

        instr = op(self, node, operand)
        instr.akitype = operand.akitype
        instr.akinode = node
        instr.akinode.name = f'op "{node.op}"'
        return instr

    def _codegen_UnOp_Not(self, node, operand):
        """
        Generate a NOT operation for a true/false value.
        """
        # if not isinstance(operand.akitype, AkiBool):
        if not self._is_type(node, operand, AkiBool):
            operand = self._scalar_as_bool(node, operand)

        xor = self.builder.xor(
            operand, self._codegen(Constant(node, 1, operand.akitype))
        )

        xor.akitype = self.types["bool"]
        xor.akinode = node
        xor.akinode.name = f'op "{node.op}"'
        return xor

    _unops = {"-": _codegen_UnOp_Neg, "not": _codegen_UnOp_Not}

    def _codegen_BinOpComparison(self, node):
        """
        Generate a comparison instruction (boolean result) for an op.
        """

        lhs = self._codegen(node.lhs)
        rhs = self._codegen(node.rhs)

        # Type checking for operation
        lhs_atype, rhs_atype = self._type_check_op(node, lhs, rhs)
        signed_op = lhs_atype.signed

        # Find and add appropriate instruction

        try:
            instr_name = lhs_atype.comp_ins
            if instr_name is None:
                raise LocalException
            instr_type = getattr(self.builder, instr_name)
            op_name = lhs_atype.comp_ops.get(node.op, None)
            if op_name is None:
                raise LocalException

        except LocalException:
            raise AkiOpError(
                node,
                self.text,
                f'Comparison operator "{CMD}{node.op}{REP}" not supported for type "{CMD}{lhs_atype}{REP}"',
            )

        instr = instr_type(node.op, lhs, rhs, op_name)

        instr.akitype = self.types["bool"]
        instr.akinode = node
        instr.akinode.name = f'op "{node.op}"'

        return instr

    def _codegen_BinOp(self, node):
        """
        Codegen a generic binary operation, typically math.
        """
        lhs = self._codegen(node.lhs)
        rhs = self._codegen(node.rhs)

        # Type checking for operation
        lhs_atype, rhs_atype = self._type_check_op(node, lhs, rhs)
        signed_op = lhs_atype.signed

        # Generate instructions for a binop that yields
        # a value of the same type as the inputs.
        # Use math_ops property of the Aki type class.

        try:
            instr_type = lhs_atype
            op_types = getattr(lhs_atype, "math_ops", None)
            if op_types is None:
                raise LocalException
            math_op = op_types.get(node.op, None)
            if math_op is None:
                raise LocalException
            instr_call = getattr(lhs_atype.__class__, f"math_op_{math_op}op")
            instr = instr_call(lhs_atype, self, node, lhs, rhs, node.op)
            # (Later for custom types we'll try to generate a call)

        except LocalException:
            raise AkiOpError(
                node,
                self.text,
                f'Binary operator "{CMD}{node.op}{REP}" not found for type "{CMD}{lhs_atype}{REP}"',
            )

        instr.akitype = instr_type
        instr.akinode = node
        instr.akinode.name = f'op "{node.op}"'
        return instr

        # TODO: This assumes the left-hand side will always have the correct
        # type information to be propagated. Need to confirm this.

    #################################################################
    # Values
    #################################################################

    def _codegen_Assignment(self, node):
        """
        Assign value to variable pointer.
        Note that we do not codegen `lhs`, since in theory
        we already have that as a named value.
        """

        lhs = node.lhs
        rhs = node.rhs

        if not isinstance(lhs, Name):
            raise AkiOpError(
                node,
                self.text,
                f'Assignment target "{CMD}{node.lhs}{REP}" must be a variable',
            )

        ptr = self._name(node.lhs, lhs.name)
        val = self._codegen(rhs)
        self._type_check_op(node, ptr, val)
        self.builder.store(val, ptr)
        return val

    def _codegen_Name(self, node, load_from_ptr=True):
        """
        Generate a variable reference from a name.
        This always assumes we want the variable value associated with the name,
        not the variable's pointer.        
        """

        # Types are returned, for now, as their enum

        named_type = self._get_type_by_name(node.name)

        # TODO: if this is a function, should we look up the registered type?

        if named_type is not None and not isinstance(named_type, AkiFunction):
            return self._codegen(Constant(node, named_type.enum_id, self.types["type"]))

        name = self._name(node, node.name)

        # Return object types as a pointer

        if self._is_type(node, name, AkiObject):
            # ... by way of a variable (ir.AllocaInstr)
            if isinstance(name, ir.AllocaInstr):
                # then load that from the pointer
                load = self.builder.load(name)
                load.akinode = name.akinode
                load.akitype = name.akitype
                return load
            # otherwise just return the object
            return name

        # Otherwise, load and decorate the value
        if load_from_ptr:
            load = self.builder.load(name)
        load.akinode = name.akinode
        load.akitype = name.akitype
        return load

    def _codegen_Constant(self, node):
        """
        Generate an LLVM `ir.Constant` value from a `Constant` AST node.
        """

        # Get the Aki variable type for the node
        vartype = self._get_vartype(node.vartype)

        # Create an LLVM constant using the derived vartype
        constant = ir.Constant(vartype.llvm_type, node.val)

        # Set the name of the Aki node to the constant value
        # (we use this in error messages, etc.)
        node.name = node.val

        # Set the Aki type for the node to the derived vartype
        node.akitype = vartype

        # Set the LLVM constant's own Aki properties
        constant.akinode = node
        constant.akitype = vartype

        return constant

    def _codegen_String(self, node):
        """
        Generates a *compile-time* string constant.
        """

        const_counter = self._const_counter()

        akitype = self._get_vartype(node.vartype)
        data, data_array = self.types["str"].data(node.val)

        # TODO: I'm considering moving this into .data
        # to keep this module leaner
        # we may also need access to it there so that we can
        # generate empty strings

        string = ir.GlobalVariable(
            self.module, data_array, f".str.data.{const_counter}"
        )
        string.initializer = ir.Constant(data_array, data)

        string.global_constant = True
        string.unnamed_addr = True

        data_object = ir.GlobalVariable(
            self.module, self.types["obj"].llvm_type, f".str.{const_counter}"
        )
        data_object.initializer = ir.Constant(
            self.types["obj"].llvm_type,
            (
                self.types["str"].enum_id,
                len(data_array),
                string.bitcast(self.typemgr.as_ptr(self.types["u_mem"]).llvm_type),
            ),
        )

        data_object.akitype = akitype
        data_object.akinode = node
        return data_object

    #################################################################
    # Builtins
    #################################################################

    # Builtins are not reserved words, but functions that cannot be
    # expressed by way of other Aki code due to low-level manipulations.
    # This list should remain as small as possible.

    # TODO: Create function signatures for these so we can auto-check
    # argument counts, types, etc.

    def _builtins_cast(self, node):
        if len(node.arguments) != 2:
            raise
        node_ref = node.arguments[0]
        target_type = node.arguments[1]

        c1 = self._codegen(node_ref)
        c2 = self._get_vartype(VarTypeName(target_type, target_type.name))

        target_data = self.typemgr.target_data()
        c1_size = c1.type.get_abi_size(target_data)
        c2_size = c2.llvm_type.get_abi_size(target_data)

        if c2_size > c1_size:
            c3 = self.builder.zext(c1, c2.llvm_type)
        elif c2_size < c1_size:
            c3 = self.builder.trunc(c1, c2.llvm_type)
        else:
            c3 = self.builder.bitcast(c1, c2.llvm_type)

        c3.akitype = c2
        c3.akinode = node
        return c3

    def _builtins_c_size(self, node):
        if len(node.arguments) != 1:
            raise
        node_ref = node.arguments[0]
        c1 = self._codegen(node_ref)
        c2 = c1.akitype.c_size(self, c1)
        return c2

    def _builtins_c_data(self, node):
        if len(node.arguments) != 1:
            raise
        node_ref = node.arguments[0]
        c1 = self._codegen(node_ref)
        c2 = c1.akitype.c_data(self, c1)
        return c2

    def _builtins_ref(self, node):
        if len(node.arguments) != 1:
            raise
        node_ref = node.arguments[0]

        if not isinstance(node_ref, Name):
            n1 = self._codegen(node_ref)
            raise AkiTypeErr(
                node_ref,
                self.text,
                f'Can\'t derive a reference as "{CMD}{n1.akinode.name}{REP}" is not a variable',
            )
        ref = self._name(node, node_ref.name)

        # if isinstance(ref.akitype, AkiFunction):
        if self._is_type(node_ref, ref, AkiFunction):
            # Function pointers are a special case, at least for now
            r1 = self._codegen(node_ref)
            r2 = self._alloca(node_ref, r1.type, f".{node_ref.name}.ref")
            self.builder.store(r1, r2)
            r2.akinode = node_ref
            r2.akitype = self.typemgr.as_ptr(r1.akitype)
            r2.akitype.llvm_type.pointee.akitype = r1.akitype
            # TODO: This should be created when we allocate the pointer, IMO
            r2.akitype.llvm_type.pointee.akitype.original_function = (
                r1.akitype.original_function
            )
            return r2

        # The `gep` creates a no-op copy of the original value so we can
        # modify its Aki properties independently. Otherwise the original
        # Aki variable reference has its properties clobbered.

        r1 = self.builder.gep(ref, [ir.Constant(ir.IntType(32), 0)])
        r1.akinode = node_ref
        r1.akitype = self.typemgr.as_ptr(ref.akitype, literal_ptr=True)
        r1.akitype.llvm_type.pointee.akitype = ref.akitype

        return r1

    def _builtins_deref(self, node):
        if len(node.arguments) != 1:
            raise

        node_deref = node.arguments[0]

        if not isinstance(node_deref, Name):
            n1 = self._codegen(node_deref)
            raise AkiTypeErr(
                node_deref,
                self.text,
                f'Can\'t extract a reference as "{CMD}{n1.akinode.name}{REP}" is not a variable',
            )

        ref = self._name(node, node_deref.name)

        # if not isinstance(ref.akitype, AkiPointer):
        if not self._is_type(node, ref, AkiPointer):
            raise AkiTypeErr(
                node_deref,
                self.text,
                f'Can\'t extract a reference as "{CMD}{node_deref.name}{REP}" is not a pointer',
            )

        f0 = self.builder.load(ref)
        f1 = self.builder.load(f0)

        f1.akinode = node_deref
        f1.akitype = ref.akitype.llvm_type.pointee.akitype
        return f1
