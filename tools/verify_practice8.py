"""Independent invariants for semantic lowering and llvmlite IR construction."""
import contextlib
import io
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.compiler import (
    Parser, SemanticChecker, CodeGen, lex, MemberCallNode, LambdaNode,
    CallNode, CompileError, main,
)
import llvmlite.binding as llvm


def checked(source):
    tree = Parser(lex(source.encode())).parse_program()
    SemanticChecker().visit(tree)
    return tree


def module(source):
    tree = checked(source)
    result = str(CodeGen().visit(tree))
    llvm.parse_assembly(result).verify()
    return result


source = Path('tests/ok/p8_task1.txt').read_text()
tree = Parser(lex(source.encode())).parse_program()
short = tree.statements[-8].value
assert type(short) is CallNode, type(short)
SemanticChecker().visit(tree)
short = tree.statements[-8].value
assert isinstance(short, MemberCallNode)
assert short.name == 'call' and short.base.name == 'triple'
# Equivalent syntax goes through precisely the same code-generation path.
assert module(source) == module(source.replace('print(triple(14))', 'print(triple.call(14))'))

for path in sorted(Path('tests/ok').glob('p8_*.txt')):
    tree = checked(path.read_text())
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        tree.dump()
    assert stream.getvalue() == path.with_suffix('.checked').read_text(), path
    text = str(CodeGen().visit(tree))
    verified = llvm.parse_assembly(text)
    verified.verify()
    for function in verified.functions:
        for block in function.blocks:
            for instruction in block.instructions:
                if instruction.opcode == 'alloca':
                    assert block.name == 'entry', (path, function.name)

text = module(Path('tests/ok/p8_task2.txt').read_text())
for fragment in (
    '%"lambda.add_k" = type {i32}',
    'define i32 @"lambda.add_k_call"(%"lambda.add_k"* %"this", i32 %"y")',
    '%"add_k" = alloca %"lambda.add_k"',
    '%"add_k.0.ptr" = getelementptr inbounds',
    'call i32 @"lambda.add_k_call"',
):
    assert fragment in text, fragment
main_ir = text.split('define i32 @"main"', 1)[1].split('\n}', 1)[0]
assert main_ir.index('store i32 100') > main_ir.index('%"add_k.0.ptr" = getelementptr')
assert main_ir.index('store i32 100') < main_ir.index('call i32 @"lambda.add_k_call"')

tree = checked(Path('tests/ok/p8_bonus.txt').read_text())
closures = [n for n in tree.statements if isinstance(n, LambdaNode)]
assert all(n.declaration.mutable for n in closures)
assert all(n.struct.methods[0].mutating for n in closures)
assert closures[1].struct.fields[0].type_name == 'lambda.next'
text = str(CodeGen().visit(tree))
assert '%"lambda.twice" = type {%"lambda.next"}' in text
assert 'load %"lambda.next"' in text

saved = sys.argv
try:
    for path in (Path('tests/ok/p8_task2.txt'), Path('tests/err/p8_missing.txt')):
        for flag in ('--ast', '--ast-checked'):
            sys.argv = ['compiler.py', flag, str(path)]
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = main()
            if path.parent.name == 'ok':
                assert status == 0 and not err.getvalue()
                assert out.getvalue() == path.with_suffix('.ast' if flag == '--ast' else '.checked').read_text()
            else:
                assert status == 1 and not out.getvalue()
                assert err.getvalue() == path.with_suffix('.expected').read_text()
finally:
    sys.argv = saved
print('Practice 8 lowering, callable equivalence, capture copies, checked AST and LLVM invariants PASS')
