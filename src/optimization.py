"""Tree-only removal of unused declarations and global functions.

Semantic links are read, never traversed as syntax. In particular, a lowered
lambda's body belongs to its generated method and is visited exactly once.
"""
from collections import Counter

from .compiler import (
    AssignNode, BlockNode, CallNode, DeclNode, FieldNode, FunctionNode,
    LambdaNode, PrintNode, ProgramNode, StructNode, VarNode, WhileNode,
)


def children(node):
    """Canonical syntax edges, excluding signatures, fields and aliases."""
    if isinstance(node, StructNode):
        return node.methods
    if isinstance(node, FunctionNode):
        return [node.body]
    if isinstance(node, LambdaNode):
        return [node.struct, node.declaration.init]
    return node.children()


def walk(node):
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(reversed(children(current)))


def execution_walk(node):
    """Nodes evaluated now; declaring a lambda does not run its body."""
    pending = [node]
    while pending:
        current = pending.pop()
        yield current
        if isinstance(current, LambdaNode):
            pending.append(current.declaration.init)
        elif not isinstance(current, (FunctionNode, StructNode)):
            pending.extend(reversed(current.children()))


def assignment_root(node):
    target = node.target
    while isinstance(target, FieldNode):
        target = target.base
    return target.decl


class EffectAnalysis:
    """Conservative call-graph fixpoint, including possible nontermination."""
    def __init__(self, tree):
        functions = [n for n in walk(tree) if isinstance(n, FunctionNode)]
        self.graph = {function: set() for function in functions}
        self.effectful = set()
        for function in functions:
            if getattr(function, 'mutating', False):
                self.effectful.add(function)
            for node in execution_walk(function.body):
                if isinstance(node, (PrintNode, WhileNode)):
                    self.effectful.add(function)
                if isinstance(node, CallNode):
                    callee = getattr(node, 'function', None)
                    if callee is None:  # read(), or an unknown external: keep.
                        self.effectful.add(function)
                    else:
                        self.graph[function].add(callee)
        # Every vertex on a cycle may fail to return, even without IO.
        # An iterative search avoids using Python's recursion stack here.
        for function in functions:
            pending = list(self.graph[function])
            seen = set()
            while pending:
                callee = pending.pop()
                if callee is function:
                    self.effectful.add(function)
                    break
                if callee not in seen:
                    seen.add(callee)
                    pending.extend(self.graph.get(callee, ()))
        changed = True
        while changed:
            changed = False
            for function, callees in self.graph.items():
                if function not in self.effectful and any(
                    callee in self.effectful or callee not in self.graph
                    for callee in callees
                ):
                    self.effectful.add(function)
                    changed = True

    def has_effect(self, expression):
        for node in execution_walk(expression):
            if isinstance(node, CallNode):
                callee = getattr(node, 'function', None)
                if callee not in self.graph or callee in self.effectful:
                    return True
        return False


class UseCounter:
    """Counts reads by id(declaration), never by source spelling."""
    def __init__(self, effects=None):
        self.reads = Counter()
        self.calls = Counter()
        self.declarations = {}
        self.functions = {}
        self.effects = effects

    def has_effect(self, expression):
        if self.effects is not None:
            return self.effects.has_effect(expression)
        return any(isinstance(node, CallNode) for node in execution_walk(expression))

    def visit(self, node):
        if type(node) is DeclNode:
            key = id(node)
            self.declarations[key] = node
            if self.has_effect(node.init):
                self.reads[key] += 1
        if type(node) is FunctionNode:
            self.functions[id(node)] = node
        if isinstance(node, VarNode):
            self.reads[id(node.decl)] += 1
        if isinstance(node, CallNode) and hasattr(node, 'function'):
            self.calls[id(node.function)] += 1
        if isinstance(node, AssignNode):
            if self.has_effect(node.value):
                self.reads[id(assignment_root(node))] += 1
            # Assignment targets (including field roots) are writes, not reads.
            self.visit(node.value)
            return
        for child in children(node):
            self.visit(child)


class Pruner:
    def __init__(self, dead_declarations, dead_functions):
        self.dead_declarations = dead_declarations
        self.dead_functions = dead_functions

    def visit(self, node):
        if isinstance(node, (ProgramNode, BlockNode)):
            node.statements = [
                statement for statement in node.statements
                if not (
                    id(statement) in self.dead_declarations
                    or id(statement) in self.dead_functions
                    or (isinstance(statement, AssignNode)
                        and id(assignment_root(statement)) in self.dead_declarations)
                )
            ]
        for child in children(node):
            self.visit(child)


class UnusedRemover:
    def __init__(self, analyze_effects=True):
        self.analyze_effects = analyze_effects
        # Numeric evidence only: retaining removed nodes here would prevent GC.
        self.rounds = []

    def run(self, tree):
        while True:
            effects = EffectAnalysis(tree) if self.analyze_effects else None
            counter = UseCounter(effects)
            counter.visit(tree)
            dead_declarations = {key for key in counter.declarations if not counter.reads[key]}
            dead_functions = {key for key in counter.functions if not counter.calls[key]}
            self.rounds.append((len(dead_declarations), len(dead_functions)))
            if not dead_declarations and not dead_functions:
                return tree
            Pruner(dead_declarations, dead_functions).visit(tree)
            # A removed global can contain lambdas. Drop their registry aliases
            # too, or codegen would emit orphan methods with dangling calls.
            active = {id(n.struct) for n in walk(tree) if isinstance(n, LambdaNode)}
            tree.generated_structs = [s for s in tree.generated_structs if id(s) in active]


def remove_unused(tree, analyze_effects=True):
    return UnusedRemover(analyze_effects).run(tree)
