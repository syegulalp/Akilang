from llvmlite import ir
from core.akitypes import (
    AkiProperties,
    AkiBool,
    AkiInt,
    AkiUnsignedInt,
    AkiFloat,
    AkiDouble,
    AkiBaseInt,
    AkiBaseFloat,
    DefaultType,
    AkiTypes,
    AkiFunction,
    AkiObject,
)
from core.astree import (
    VarType,
    LLVMOp,
    BinOpComparison,
    Constant,
    IfExpr,
    LLVMInstr,
    Name,
    VarList,
    Assignment,
)
from core.error import AkiNameErr, AkiTypeErr, AkiOpError, AkiBaseErr, AkiSyntaxErr


class FuncState:
    """
    Object for storing function state, such as its symbol table,
    and context information such as the decorator stack and 
    `unsafe` states.
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

    def __init__(self, module=None):

        # Create an LLVM module if we aren't passed one.

        if not module:
            self.module = ir.Module()
        else:
            self.module = module

        self.fn = None
        self.text = None

    def init_func_handlers(self):

        # Initialize function state handlers.

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

    def _codegen_LLVMInstr(self, node):
        return node.llvm_instr

    def _name(self, node, name_to_find):
        """
        Retrieve a name reference, not the underlying value,
        from the symbol table or the list of globals.
        """

        # First, look in the symbol table:

        name = self.fn.symtab.get(name_to_find, None)

        if name is None:
            name = self.module.globals.get(name_to_find, None)

        if name is None:
            raise AkiNameErr(node, self.text, f'Name "{name_to_find}" not found')

        return name

    def _aki(self, node, llvm_obj):
        pass

        # Take in an LLVM object
        # and an Aki node
        # to LLVM, add .aki_node and .aki_type
        # .aki_node = the node from the AST
        # if none exists, generate one
        # .aki_type = vartype from lookup

        # should we do .aki.node, .aki.type?

    def _add_node_props(self, node: VarType):
        """
        Takes in a single AST VarType node,
        and adds Aki and LLVM type information to it,
        based on its native `.vartype` string.        
        """

        # look up the string ID

        v = node.vartype

        if v is None:
            vartype = DefaultType
        else:
            vartype = getattr(AkiTypes, v, None)

        if vartype is None:
            raise AkiTypeErr(
                node, self.text, f'Unrecognized type definition "{vartype}"'
            )

        node.aki_type = vartype
        node.llvm_type = vartype.llvm_type

    #### Top-level statements

    def _codegen_Prototype(self, node):
        """
        Generate a function prototype for the LLVM module
        from the Prototype AST node.
        """

        # Name collision check

        if node.name in self.module.globals:
            raise AkiNameErr(
                node, self.text, f'Name "{node.name}" already exists in this module"'
            )

        # Generate function arguments.
        # Add LLVM type information to each argument,
        # based on the type information available in the node.

        func_args = []

        for _ in node.arguments:
            self._add_node_props(_.vartype)
            func_args.append(_.vartype.llvm_type)

        # Set return type.

        self._add_node_props(node.return_type)
        return_type = node.return_type

        # Generate function prototype.

        proto = ir.Function(
            self.module,
            ir.FunctionType(return_type.llvm_type, func_args),
            name=node.name,
        )

        # Set variable types for function

        proto.aki = node
        function_type = AkiFunction(proto)
        proto.aki.vartype = VarType(node, str(function_type))
        proto.aki.vartype.aki_type = function_type

        return proto

    def _codegen_Function(self, node):
        """
        Generate an LLVM function from a Function AST node.
        """

        self.init_func_handlers()

        # Generate function prototype.

        func = self._codegen(node.prototype)
        self.fn.fn = func

        # Generate entry block and function body.

        self.entry_block = func.append_basic_block("entry")
        self.builder = ir.IRBuilder(self.entry_block)

        # Add prototype arguments to function symbol table
        # and add references in function.
        # Use isinstance(ir.Argument) to determine if the
        # var being looked up is a func arg.

        for a, b in zip(func.args, node.prototype.arguments):
            var_alloc = self.builder.alloca(b.vartype.llvm_type, None, b.name)
            var_alloc.aki = b
            a.aki = b
            self.fn.symtab[b.name] = var_alloc
            self.builder.store(a, var_alloc)

        # Add return value holder.

        self.fn.return_value = self.builder.alloca(
            func.return_value.type, None, ".function_return_value"
        )

        # Set Akitype values for the return value holder
        # and for the function's actual return value.

        # return_value should be a synthetic node

        self.fn.return_value.aki = func.aki
        func.return_value.aki = self.fn.return_value.aki

        # Create actual starting function block and codegen instructions.

        self.body_block = func.append_basic_block("body")
        self.builder.branch(self.body_block)
        self.builder.position_at_start(self.body_block)

        result = self._codegen(node.body)

        # If we have an empty function body,
        # load the default value for the return type
        # and return that.

        if result is None:
            result = self._codegen_Constant(
                Constant(
                    node.body.p,
                    node.prototype.return_type.aki_type.default(),
                    node.prototype.return_type,
                )
            )

        # If we don't explicitly assign a return type on the function prototype,
        # we infer it from the return value of the body.
        # Otherwise, if there's a mismatch, we error out.

        if result.aki.vartype.aki_type != self.fn.return_value.aki.return_type.aki_type:

            if node.prototype.return_type.vartype is None:
                func.ftype.return_type = result.type
                func.return_value.type = result.type
                func.return_value.aki.return_type.aki_type = result.aki.vartype.aki_type

                # this needs to be a synthetic node?
                # or set wholly manually?

                self.fn.return_value.type = result.type.as_pointer()
                self.fn.return_value.aki.return_type.aki_type = (
                    result.aki.vartype.aki_type
                )

            else:
                raise AkiTypeErr(
                    node,
                    self.text,
                    f"Return value from function (type{result.aki.vartype.aki_type}) does not match function signature return type (type{self.fn.return_value.aki.vartype.aki_type}) ",
                )

        # Add return value for function in exit block,
        # branch to exit, return the return value.

        # If this is an allocation, we need to unload it first.

        if isinstance(result, ir.AllocaInstr):
            result = self.builder.load(result)

        self.builder.store(result, self.fn.return_value)

        exit_block = func.append_basic_block("exit")
        self.builder.branch(exit_block)

        self.builder.position_at_start(exit_block)
        self.builder.ret(self.builder.load(self.fn.return_value, ".ret"))

        # Reset function state handlers.

        self.fn = None

        return func

    ### Declarations

    def _codegen_VarList(self, node):
        for _ in node.vars:

            # Create defaults if no value or vartype

            if _.val is None:
                if _.vartype is None:
                    _.vartype = VarType(_.p, DefaultType.type_id)
                    self._add_node_props(_.vartype)
                _.val = Constant(
                    _.p, _.vartype.aki_type.default(), VarType(_.p, _.vartype.vartype)
                )
            else:
                self._add_node_props(_.vartype)

            # Create an allocation for that type
            var_ptr = self.builder.alloca(_.vartype.llvm_type, None, _.name)
            # and store its node attributes
            var_ptr.aki = _

            # Store the variable in the function symbol table
            self.fn.symtab[_.name] = var_ptr

            # and store the value itself to the variable
            value = self._codegen(_.val)
            self.builder.store(value, var_ptr)

    #### Control flow

    def _codegen_Break(self, node):

        if len(self.fn.breakpoints) == 0:
            raise AkiSyntaxErr(
                node, self.text, f'"break" not called within a loop block'
            )

        self.builder.branch(self.fn.breakpoints[-1])

    def _codegen_LoopExpr(self, node):

        local_symtab = {}

        # If there are no elements in the loop declaration,
        # assume an infinite loop

        if node.conditions == []:

            start = None
            stop = None
            step = None

        else:

            # Create the loop initialization block

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
            del self.fn.symtab[_]

        return loop_body

    def _codegen_IfExpr(self, node):

        if node.then_expr.vartype != node.else_expr.vartype:
            raise AkiTypeErr(
                node.then_expr,
                self.text,
                '"if/else" must yield same type; use "when/else" for results of different types',
            )

        self._add_node_props(node.then_expr.vartype)
        if_result = self.builder.alloca(
            node.then_expr.vartype.llvm_type, name="if_result"
        )

        if_expr = self._codegen(node.if_expr)

        if not isinstance(if_expr.aki.vartype.aki_type, AkiBool):

            if_expr = self._codegen(
                BinOpComparison(
                    node.if_expr,
                    "!=",
                    LLVMInstr(node.if_expr, if_expr),
                    Constant(
                        node.if_expr,
                        if_expr.aki.vartype.aki_type.default(),
                        if_expr.aki.vartype,
                    ),
                )
            )

        with self.builder.if_else(if_expr) as (then_clause, else_clause):
            with then_clause:
                then_result = self._codegen(node.then_expr)
                self.builder.store(then_result, if_result)
            with else_clause:
                else_result = self._codegen(node.else_expr)
                self.builder.store(else_result, if_result)

        result = self.builder.load(if_result)
        result.aki = LLVMOp(
            node.if_expr, node.then_expr.vartype.aki_type, f"if operation"
        )

        return result

    def _codegen_WhenExpr(self, node):
        if_expr = self._codegen(node.if_expr)

        if not isinstance(if_expr.aki.vartype.aki_type, AkiBool):

            if_expr = self._codegen(
                BinOpComparison(
                    node.if_expr,
                    "!=",
                    LLVMInstr(node.if_expr, if_expr),
                    Constant(
                        node.if_expr,
                        if_expr.aki.vartype.aki_type.default(),
                        if_expr.aki.vartype,
                    ),
                )
            )

        with self.builder.if_else(if_expr) as (then_clause, else_clause):
            with then_clause:
                then_result = self._codegen(node.then_expr)
            with else_clause:
                if node.else_expr:
                    else_result = self._codegen(node.else_expr)

        return if_expr

    #### Operations

    def _codegen_Assignment(self, node):

        lhs = node.lhs
        rhs = node.rhs

        if not isinstance(lhs, Name):
            raise AkiOpError(node, self.text, f"Assignment target must be a variable")

        ptr = self._name(node.lhs, lhs.name)
        val = self._codegen(rhs)
        self.builder.store(val, ptr)
        return ptr

    def _codegen_ExpressionBlock(self, node):
        result = None
        for _ in node.body:
            result = self._codegen(_)
        return result

    def _codegen_BinOpComparison(self, node):
        return self._codegen_BinOp(node)

    def _codegen_Call(self, node):
        """
        Generate a function call from a Call node.
        """

        call_func = self._name(node, node.name)

        args = []

        if len(call_func.args) != len(node.arguments):
            raise AkiBaseErr(
                node,
                self.text,
                f'Function call to "{node.name}" expected {len(call_func.args)} arguments but got {len(node.arguments)}',
            )

        for id, arg in enumerate(node.arguments):
            arg_val = self._codegen(arg)
            arg_val.aki = arg
            if arg_val.type != call_func.args[id].type:
                raise AkiTypeErr(
                    arg,
                    self.text,
                    f'Value "{arg.name}" of type "{arg_val.aki.vartype.aki_type}" does not match function argument {id+1} of type "{call_func.args[id].aki.vartype.aki_type}"',
                )

            args.append(arg_val)

        call = self.builder.call(call_func, args, call_func.name + ".call")
        call.aki = LLVMOp(
            node, call_func.aki.return_type.aki_type, f"{call_func.name}()"
        )

        return call

    def _codegen_UnOp(self, node):
        """
        Generate a unary op from an AST UnOp node.
        """

        op = self.unops.get(node.op, None)

        if op is None:
            raise AkiOpError(node, self.text, f'Operator "{node.op}" not yet supported')

        operand = self._codegen(node.lhs)
        instr = op(self, node, operand)
        return instr

    def _codegen_UnOp_Neg(self, node, operand):
        """
        Generate a unary negation operation for a scalar value.
        """

        lhs = self._codegen(Constant(node, 0, operand.aki.vartype))

        if isinstance(operand.aki.vartype.aki_type, AkiInt):
            instr = self.builder.sub(lhs, operand, "negop")
        elif isinstance(operand.aki.vartype.aki_type, AkiFloat):
            instr = self.builder.fsub(lhs, operand, "fnegop")
        elif isinstance(operand.aki.vartype.aki_type, AkiDouble):
            instr = self.builder.fsub(lhs, operand, "fnegop")

        instr.aki = LLVMOp(
            node.lhs, operand.aki.vartype.aki_type, f"{node.op} operation"
        )

        return instr

    def _codegen_UnOp_Not(self, node, operand):
        """
        Generate a NOT operation for a scalar value.
        """

        if not isinstance(operand.aki.vartype.aki_type, AkiBool):

            operand = self._codegen(
                BinOpComparison(
                    node,
                    "!=",
                    LLVMInstr(node, operand),
                    Constant(
                        node,
                        operand.aki.vartype.aki_type.default(),
                        operand.aki.vartype,
                    ),
                )
            )

        xor = self.builder.xor(
            operand, self._codegen(Constant(node, 1, operand.aki.vartype))
        )
        xor.aki = LLVMOp(node, operand.aki.vartype.aki_type, f"{node.op} operation")

        return xor

    def _codegen_BinOp(self, node):
        """
        Generate a binop, typically a math operation,
        from an AST BinOp node.

        Variable assignments or in-place operations
        are not handled here. Assignments have 
        their own AST node, Assign; in-place ops are
        converted to Assign nodes with a BinOp expression
        as the value.
        """

        lhs = self._codegen(node.lhs)
        rhs = self._codegen(node.rhs)

        # Type checking for operation

        lhs_atype = lhs.aki.vartype.aki_type
        rhs_atype = rhs.aki.vartype.aki_type

        if lhs_atype != rhs_atype:

            error = f'"{lhs.aki.name}" (type{lhs_atype}) and "{rhs.aki.name}" (type{rhs_atype}) do not have compatible types for operation "{node.op}".'

            if lhs_atype.signed != rhs_atype.signed:
                is_signed = lambda x: "Signed" if x else "Unsigned"
                error += f'\nSigned/unsigned disagreement:\n - "{lhs.aki.name}" (type{lhs_atype}): {is_signed(lhs_atype.signed)}\n - "{rhs.aki.name}" (type{rhs_atype}): {is_signed(rhs_atype.signed)}'

            raise AkiTypeErr(node, self.text, error)

        signed_op = lhs_atype.signed

        # Add appropriate instruction

        instr = None

        if isinstance(node, BinOpComparison):

            # Generate instructions for a comparison operation,
            # which yields a boolean value.

            if isinstance(lhs_atype, AkiBaseFloat):
                op = self.builder.fcmp_ordered
            elif isinstance(lhs_atype, (AkiBaseInt, AkiBool)):
                if lhs_atype.signed:
                    op = self.builder.icmp_signed
                else:
                    op = self.builder.icmp_unsigned
            else:
                raise AkiOpError(
                    node,
                    self.text,
                    f'Comparison operator "{node.op}" not supported for type "{lhs_atype}"',
                )

            instr_type = AkiBool()

            if node.op == "==":
                instr = op("==", lhs, rhs, ".eqop")
            elif node.op == "!=":
                instr = op("!=", lhs, rhs, ".neqop")
            elif node.op == "<=":
                instr = op("<=", lhs, rhs, ".leqop")
            elif node.op == ">=":
                instr = op(">=", lhs, rhs, ".geqop")
            elif node.op == "<":
                instr = op("<", lhs, rhs, ".lt")
            elif node.op == ">":
                instr = op(">", lhs, rhs, ".gt")

        else:

            # Generate instructions for a binop that yields
            # a value of the same type as the inputs.

            instr_type = lhs_atype

            if isinstance(lhs_atype, (AkiBaseInt, AkiBool)):
                if node.op == "+":
                    instr = self.builder.add(lhs, rhs, ".addop")
                elif node.op == "-":
                    instr = self.builder.sub(lhs, rhs, ".subop")
                elif node.op == "*":
                    instr = self.builder.mul(lhs, rhs, ".mulop")
                elif node.op == "/":
                    # XXX: trap unsigned division
                    instr = self.builder.sdiv(lhs, rhs, ".divop")
                elif node.op == "&":
                    instr = self.builder.and_(lhs, rhs, ".bin_andop")
                elif node.op == "|":
                    instr = self.builder.or_(lhs, rhs, ".bin_orop")

                elif node.op in ("and", "or"):

                    if not isinstance(lhs.aki.vartype.aki_type, AkiBool):

                        operand = self._codegen(
                            BinOpComparison(
                                node.lhs,
                                "!=",
                                LLVMInstr(node.lhs, lhs),
                                Constant(
                                    node.lhs,
                                    lhs.aki.vartype.aki_type.default(),
                                    lhs.aki.vartype,
                                ),
                            )
                        )

                    else:
                        operand = lhs

                    if node.op == "and":
                        true_op = LLVMInstr(node.rhs, rhs)
                        false_op = LLVMInstr(node.lhs, lhs)

                    else:
                        true_op = LLVMInstr(node.lhs, lhs)
                        false_op = LLVMInstr(node.rhs, rhs)

                    result_test = self._codegen(
                        IfExpr(
                            operand.aki,
                            LLVMInstr(operand.aki, operand),
                            true_op,
                            false_op,
                        )
                    )

                    instr = result_test
                    instr_type = lhs_atype

            elif isinstance(lhs_atype, AkiBaseFloat):
                if node.op == "+":
                    instr = self.builder.fadd(lhs, rhs, ".faddop")
                elif node.op == "-":
                    instr = self.builder.fsub(lhs, rhs, ".fsubop")
                elif node.op == "*":
                    instr = self.builder.fmul(lhs, rhs, ".fmulop")
                elif node.op == "/":
                    instr = self.builder.fdiv(lhs, rhs, ".fdivop")

        if instr is None:
            raise AkiOpError(
                node,
                self.text,
                f'Binary operator "{node.op}" not found for type "{lhs_atype}"',
            )

        instr.aki = LLVMOp(node.lhs, instr_type, f"{node.op} operation")
        return instr

        # TODO: This assumes the left-hand side will always have the correct
        # type information to be propagated. Need to confirm this.

    #### Values

    def _codegen_Name(self, node):
        """
        Generate a variable reference from a name.
        This always assumes we want the variable value associated with the name,
        not the variable's pointer.        
        """
        name = self._name(node, node.name)

        # Return object types as a pointer

        if isinstance(name.aki.vartype.aki_type, AkiObject):
            return name

        # Otherwise, load and decorate the value

        load = self.builder.load(name)
        load.aki = name.aki
        return load

    def _codegen_Constant(self, node):
        """
        Generate an LLVM ir.Constant value from a Constant AST node.
        """

        self._add_node_props(node.vartype)
        constant = ir.Constant(node.vartype.llvm_type, node.val)
        constant.aki = node
        node.name = node.val
        return constant

    unops = {"-": _codegen_UnOp_Neg, "not": _codegen_UnOp_Not}
