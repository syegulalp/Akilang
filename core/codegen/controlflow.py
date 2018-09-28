from core.ast_module import Var, Binary, Variable, Number
from core.vartypes import SignedInt
from core.errors import CodegenError, ParseError
from core.tokens import Builtins, Dunders
from core.mangling import mangle_types

import llvmlite.ir as ir

# pylint: disable=E1101

class ControlFlow():
    def _codegen_Return(self, node):
        '''
        Generates a return from within a function, and 
        sets the `self.func_returncalled` flag
        to notify that a return has been triggered.
        '''

        retval = self._codegen(node.val)
        if self.func_returntype is None:
            raise CodegenError(f'Unknown return declaration error', 
                node.position)

        if retval.type != self.func_returntype:
            raise CodegenError(
                f'In function "{self.func_incontext.public_name}", expected return type "{self.func_returntype.describe()}" but got "{retval.type.describe()}" instead',
                node.val.position)

        self.builder.store(retval, self.func_returnarg)
        self.builder.branch(self.func_returnblock)
        self.func_returncalled = True

        # Check for the presence of a returned object
        # that requires memory tracing
        # if so, add it to the set of functions that returns a trackable object

        to_check = self._extract_operand(retval)

        if to_check.tracked:
            self.gives_alloc.add(self.func_returnblock.parent)
            self.func_returnblock.parent.returns.append(to_check)

    def _codegen_Match(self, node):
        cond_item = self._codegen(node.cond_item)
        default = ir.Block(self.builder.function, 'defaultmatch')
        exit = ir.Block(self.builder.function, 'endmatch')
        switch_instr = self.builder.switch(cond_item, default)
        cases = []
        exprs = {}
        values = set()
        for value, expr in node.match_list:
            val_codegen = self._codegen(value)
            if not isinstance(val_codegen, ir.values.Constant):
                raise CodegenError(
                    f'Match parameter must be a constant, not an expression',
                    value.position)
            if val_codegen.type != cond_item.type:
                raise CodegenError(
                    f'Type of match object ("{cond_item.type.describe()}") and match parameter ("{val_codegen.type.describe()}") must be consistent)',
                    value.position)
            if val_codegen.constant in values:
                raise CodegenError(
                    f'Match parameter {value} duplicated',
                    value.position
                )
            values.add(val_codegen.constant)
            if expr in exprs:
                switch_instr.add_case(val_codegen, exprs[expr])
            else:
                n = ir.Block(self.builder.function, 'match')
                switch_instr.add_case(val_codegen, n)
                exprs[expr] = n                
                cases.append([n, expr])
        for block, expr in cases:
            self.builder.function.basic_blocks.append(block)
            self.builder.position_at_start(block)
            result = self._codegen(expr, False)
            #if result and not self.builder.block.is_terminated:
            if not self.builder.block.is_terminated:
                self.builder.branch(exit)
        self.builder.function.basic_blocks.append(default)
        self.builder.position_at_start(default)
        if node.default:
            self._codegen(node.default, False)
        if not self.builder.block.is_terminated:
            self.builder.branch(exit)
        self.builder.function.basic_blocks.append(exit)
        self.builder.position_at_start(exit)
        return cond_item

    def _codegen_When(self, node):
        return self._codegen_If(node, True)

    def _codegen_If(self, node, codegen_when=False):
        # Emit comparison value

        cond_val = self._codegen(node.cond_expr)

        if_type = cond_val.type

        cond = ('!=', cond_val, ir.Constant(if_type, 0), 'notnull')

        if isinstance(if_type, (ir.FloatType, ir.DoubleType)):
            cmp_instr = self.builder.fcmp_unordered(*cond)
        elif isinstance(if_type, SignedInt):
            cmp_instr = self.builder.icmp_signed(*cond)
        else:
            cmp_instr = self.builder.icmp_unsigned(*cond)

        # Create basic blocks to express the control flow
        then_bb = ir.Block(self.builder.function, 'then')
        else_bb = ir.Block(self.builder.function, 'else')
        merge_bb = ir.Block(self.builder.function, 'endif')

        # branch to either then_bb or else_bb depending on cmp
        # if no else, then go straight to merge
        if node.else_expr is None:
            self.builder.cbranch(cmp_instr, then_bb, merge_bb)
        else:
            self.builder.cbranch(cmp_instr, then_bb, else_bb)

        # Emit the 'then' part
        self.builder.function.basic_blocks.append(then_bb)
        self.builder.position_at_start(then_bb)

        self.breaks = False

        then_val = self._codegen(node.then_expr, False)
        #if then_val or not self.builder.block.is_terminated:
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_bb)           

        # Emission of then_val could have generated a new basic block
        # (and thus modified the current basic block).
        # To properly set up the PHI, remember which block the 'then' part ends in.
        then_bb = self.builder.block

        # Emit the 'else' part, if needed

        if node.else_expr is None:
            else_val = None
        else:
            self.builder.function.basic_blocks.append(else_bb)
            self.builder.position_at_start(else_bb)
            else_val = self._codegen(node.else_expr)
            #if else_val or not self.builder.block.is_terminated:
            if not self.builder.block.is_terminated:
                self.builder.branch(merge_bb)
            else_bb = self.builder.block

        # check for an early return,
        # prune unneeded phi operations

        self.builder.function.basic_blocks.append(merge_bb)
        self.builder.position_at_start(merge_bb)

        if then_val is None and else_val is None:
            # returns are present in each branch
            return
        elif not else_val:
            # return present in 1st branch only
            return then_val.type
        elif not then_val:
            # return present in 2nd branch only
            return else_val.type
        # otherwise no returns in any branch

        if codegen_when:
            return cond_val

        # make sure then/else are in agreement
        # so we're returning consistent types

        if then_val.type != else_val.type:
            raise CodegenError(
                f'"then/else" expression return types must be the same ("{then_val.type.describe()}" does not match "{else_val.type.describe()}"',
                node.position)

        phi = self.builder.phi(then_val.type, 'ifval')
        phi.add_incoming(then_val, then_bb)
        phi.add_incoming(else_val, else_bb)
        return phi

    def _codegen_Break(self, node):
        exit = self.loop_exit[-1][0]
        self.breaks = True
        self.builder.branch(exit)

    def _codegen_Loop(self, node):
        # Output this as:
        #   ...
        #   start = startexpr
        #   goto loopcond
        # loopcond:
        #   variable = phi [start, loopheader], [nextvariable, loopbody]
        #   step = stepexpr (or variable + 1)
        #   nextvariable = step
        #   endcond = endexpr
        #   br endcond, loopbody, loopafter
        # loopbody:
        #   bodyexpr
        #   jmp loopcond
        # loopafter:
        #   return variable

        # Define blocks
        loopcond_bb = ir.Block(self.builder.function, 'loopcond')
        loopbody_bb = ir.Block(self.builder.function, 'loopbody')
        loopcounter_bb = ir.Block(self.builder.function, 'loopcounter')
        loopafter_bb = ir.Block(self.builder.function, 'loopafter')

        # If this loop has no conditions, codegen it with a manual exit

        if node.start_expr is None:
            self.builder.branch(loopbody_bb)
            self.builder.function.basic_blocks.append(loopbody_bb)
            self.builder.position_at_start(loopbody_bb)
            self.loop_exit.append(
                (loopafter_bb, loopbody_bb)
            )
            self._codegen(node.body, False)
            self.loop_exit.pop()            
            if not self.builder.block.is_terminated:
                self.builder.branch(loopbody_bb)
            self.builder.function.basic_blocks.append(loopafter_bb)
            self.builder.position_at_start(loopafter_bb)
            return
        else:
            self.loop_exit.append(
                (loopafter_bb, loopcounter_bb)
            )

        # ###########
        # loop header
        #############

        var_addr = self._varaddr(node.start_expr.name, False)
        if var_addr is None:
            self._codegen_Var(Var(node.start_expr.position, [node.start_expr]))
            var_addr = self._varaddr(node.start_expr.name, False)
        else:
            self._codegen_Assignment(
                node.start_expr,
                node.start_expr.initializer
            )

        loop_ctr_type = var_addr.type.pointee

        # Jump to loop cond
        self.builder.branch(loopcond_bb)

        ###########
        # loop cond
        ###########

        self.builder.function.basic_blocks.append(loopcond_bb)
        self.builder.position_at_start(loopcond_bb)

        # Set the symbol table to to reach de local counting variable.
        # If it shadows an existing variable, save it before and restore it later.
        oldval = self.func_symtab.get(node.start_expr.name)
        self.func_symtab[node.start_expr.name] = var_addr

        # Compute the end condition
        endcond = self._codegen(node.end_expr)

        # TODO: this requires different comparison operators
        # based on the type of the loop object - int vs. float, chiefly
        # this is a pattern we may repeat too often

        cond = ('!=', endcond, ir.Constant(loop_ctr_type, 0), 'loopifcond')

        if isinstance(loop_ctr_type, (ir.FloatType, ir.DoubleType)):
            cmp_instr = self.builder.fcmp_unordered(*cond)
        elif isinstance(loop_ctr_type, ir.IntType):
            if getattr(loop_ctr_type, 'v_signed', None):
                cmp_instr = self.builder.icmp_signed(*cond)
            else:
                cmp_instr = self.builder.icmp_unsigned(*cond)

        # Goto loop body if condition satisfied, otherwise, exit.
        self.builder.cbranch(cmp_instr, loopbody_bb, loopafter_bb)

        ############
        # loop body
        ############

        self.builder.function.basic_blocks.append(loopbody_bb)
        self.builder.position_at_start(loopbody_bb)

        # Emit the body of the loop.
        # Note that we ignore the value computed by the body.
        self._codegen(node.body, False)

        # If the step is unknown, make it increment by 1
        if node.step_expr is None:
            node.step_expr = Binary(node.position, "+",
                                    Variable(node.position,
                                             node.start_expr.name),
                                    Number(None, 1, loop_ctr_type))

        self.builder.branch(loopcounter_bb)

        ###############
        # loop counter
        ###############

        self.builder.function.basic_blocks.append(loopcounter_bb)
        self.builder.position_at_start(loopcounter_bb)
        
        # Evaluate the step and update the counter
        nextval = self._codegen(node.step_expr)
        self.builder.store(nextval, var_addr)

        # Goto loop cond
        self.builder.branch(loopcond_bb)

        #############
        # loop after
        #############

        # New code will be inserted into a new block
        self.builder.function.basic_blocks.append(loopafter_bb)
        self.builder.position_at_start(loopafter_bb)

        # Remove the loop variable from the symbol table;
        # if it shadowed an existing variable, restore that.
        if oldval is None:
            del self.func_symtab[node.start_expr.name]
        else:
            self.func_symtab[node.start_expr.name] = oldval

        # Remove topmost loop exit/loop continue marker
        #if self.loop_exit:
        self.loop_exit.pop()

        #self.loop_counter = None
        
        # The 'loop' expression returns the last value of the counter
        return self.builder.load(var_addr)

    def _codegen_Continue(self, node):
        # First, determine if we are in a loop context:

        if not self.loop_exit:
            raise CodegenError(
                '"continue" called outside of loop',
                node.position
            )

        return self.builder.branch(self.loop_exit[-1][1])

    def _codegen_While(self, node):
        # This is a modified version of a For.

        # Define blocks
        loopcond_bb = ir.Block(self.builder.function, 'loopcond')
        loopbody_bb = ir.Block(self.builder.function, 'loopbody')
        loopafter_bb = ir.Block(self.builder.function, 'loopafter')

        # ###########
        # loop header
        #############

        # Save the current block to tell the loop cond where we are coming from
        # no longer needed, I think
        #loopheader_bb = self.builder.block

        # Jump to loop cond
        self.builder.branch(loopcond_bb)

        ###########
        # loop cond
        ###########

        self.builder.function.basic_blocks.append(loopcond_bb)
        self.builder.position_at_start(loopcond_bb)

        # Compute the end condition
        endcond = self._codegen(node.cond_expr)

        type = endcond.type

        # TODO: this requires different comparison operators
        # based on the type of the loop object - int vs. float, chiefly
        # this is a pattern we may repeat too often

        cond = ('!=', endcond, ir.Constant(type, 0), 'loopcond')

        if isinstance(type, (ir.FloatType, ir.DoubleType)):
            cmp_instr = self.builder.fcmp_unordered(*cond)
        elif isinstance(type, ir.IntType):
            if getattr(type, 'v_signed', None):
                cmp_instr = self.builder.icmp_signed(*cond)
            else:
                cmp_instr = self.builder.icmp_unsigned(*cond)

        # Goto loop body if condition satisfied, otherwise, exit.
        self.builder.cbranch(cmp_instr, loopbody_bb, loopafter_bb)

        ############
        # loop body
        ############

        self.builder.function.basic_blocks.append(loopbody_bb)
        self.builder.position_at_start(loopbody_bb)

        # Emit the body of the loop.
        body_val = self._codegen(node.body, False)

        # The value of the body has to be placed into a special
        # return variable so it's valid across all code paths
        self.builder.position_at_start(loopcond_bb)
        return_var = self.builder.alloca(
            body_val.type, size=None, name='%_while_loop_return')

        # Goto loop cond
        self.builder.position_at_end(loopbody_bb)
        self.builder.store(body_val, return_var)
        self.builder.branch(loopcond_bb)

        #############
        # loop after
        #############

        # New code will be inserted into a new block
        self.builder.function.basic_blocks.append(loopafter_bb)
        self.builder.position_at_start(loopafter_bb)

        # The 'while' expression returns the value of the body
        return self.builder.load(return_var)

    def _codegen_Call(self, node, obj_method=False):
        if not obj_method:
            if node.name in Dunders:
                return self._codegen_dunder_methods(node)
            if node.name in Builtins:
                return getattr(self, '_codegen_Builtins_' + node.name)(node)            

        call_args = []
        possible_opt_args_funcs = set()

        # The reason for the peculiar construction below
        # is to first process a blank argument list, so
        # we can match calls to functions that have
        # all optional arguments

        for arg in node.args+[None]:
            _ = mangle_types(node.name, call_args)
            if _ in self.opt_args_funcs:
                possible_opt_args_funcs.add(self.opt_args_funcs[_])
            if arg:
                call_args.append(self._codegen(arg))

        if obj_method:
            c = call_args[0]
            try:
                c1 = c.type.pointee.name
            except:
                c1 = c.type
            node.name = f'{c1}.__{node.name}__'

        if not possible_opt_args_funcs:
            mangled_name = mangle_types(node.name, call_args)
            callee_func = self.module.globals.get(mangled_name, None)

        else:
            try:
                match = False
                for f1 in possible_opt_args_funcs:
                    if len(call_args) > len(f1.args):
                        continue
                    match = True
                    for function_arg, call_arg in zip(f1.args, call_args):
                        if function_arg.type != call_arg.type:
                            match = False
                            break
                if not match:
                    raise TypeError
            except TypeError:
                raise ParseError(
                    f'argument types do not match possible argument signature for optional-argument function "{f1.public_name}"',
                    node.position
                )
            else:
                callee_func = f1
                for n in range(len(call_args), len(f1.args)):
                    call_args.append(f1.args[n].default_value)

        # Determine if this is a function pointer

        try:
            
            # if we don't yet have a reference,
            # since this might be a function pointer,
            # attempt to obtain one from the variable list

            if not callee_func:
                callee_func = self._varaddr(node.name, False)

            if callee_func.type.is_func():
                # retrieve actual function pointer from the variable ref
                func_to_check = callee_func.type.pointee.pointee
                final_call = self.builder.load(callee_func)                
                ftype = func_to_check
                
                final_call.decorators = []
                #final_call.decorators = callee_func.decorators

                # It's not possible to trace decorators across
                # function pointers

            else:
                # this is a regular old function, not a function pointer
                func_to_check = callee_func
                final_call = callee_func
                ftype = getattr(func_to_check, 'ftype', None)

        except Exception:
            raise CodegenError(
                f'Call to unknown function "{node.name}" with signature "{[n.type.describe() for n in call_args]}" (maybe this call signature is not implemented for this function?)',
                node.position)

        if not ftype.var_arg:
            if len(func_to_check.args) != len(call_args):
                raise CodegenError(
                    f'Call argument length mismatch for "{node.name}" (expected {len(callee_func.args)}, got {len(node.args)})',
                    node.position)
        else:
            if len(call_args) < len(func_to_check.args):
                raise CodegenError(
                    f'Call argument length mismatch for "{node.name}" (expected at least {len(callee_func.args)}, got {len(node.args)})',
                    node.position)
        
        nomod = 'nomod' in final_call.decorators
        
        for x, n in enumerate(zip(call_args, func_to_check.args)):
            type0 = n[0].type
            
            # in some cases, such as with a function pointer,
            # the argument is not an Argument but a core.vartypes instance
            # so this check is necessary

            if type(n[1])==ir.values.Argument:
                type1 = n[1].type
            else:
                type1 = n[1]

            if type0 != type1:
                raise CodegenError(
                    f'Call argument type mismatch for "{node.name}" (position {x}: expected {type1.describe()}, got {type0.describe()})',
                    node.args[x].position)

            # if this is a traced object, and we give it away,
            # then we can't delete it in this scope anymore
            # because we no longer have ownership of it
            
            if not nomod:
                to_check = self._extract_operand(n[0])
                if to_check.heap_alloc:
                    to_check.tracked = False

        call_to_return = self.builder.call(final_call, call_args, 'calltmp')

        # Check for the presence of an object returned from the call
        # that requires memory tracing

        if callee_func in self.gives_alloc:
            call_to_return.heap_alloc = True
            call_to_return.tracked = True

        # FIXME: There ought to be a better way to assign this
        
        if callee_func.tracked == True:
            call_to_return.heap_alloc = True
            call_to_return.tracked = True

        if 'unsafe_req' in final_call.decorators and not self.allow_unsafe:
            raise CodegenError(
                f'Function "{node.name}" is decorated with "@unsafe_req" and requires an "unsafe" block"',
                node.position
            )
        
        # if callee_func.do_not_allocate == True:
        #     call_to_return.do_not_allocate = True

        # if 'nomod' in callee_func.decorators:
        #     call_to_return.tracked=False

        return call_to_return

    def _codegen_Do(self, node):
        for n in node.expr_list:
            try:
                t = self._codegen(n, False)
            except CodegenError as e:
                raise e
        return t

    def _codegen_Unsafe(self, node):
        self.allow_unsafe = True
        body_val = self._codegen(node.body)
        self.allow_unsafe = False
        return body_val
    
    def _codegen_With(self, node):
        new_bindings = [v.name for v in node.vars.vars]
        
        # originally we codegenned this to allocate
        # the variable in the local block,
        # but I realized that would leak memory.
        # it's best if we just alloca in the entry
        # block in all cases.
        # the autodispose will only dispose of things
        # that have allocation tracking anyway.

        self._codegen_Var(node.vars)

        body_val = self._codegen(node.body)

        for n in reversed(new_bindings):
            self._codegen_autodispose(
                [
                [n, self.func_symtab[n]]
                ],
                None)
            del self.func_symtab[n]
    
        return body_val        