"""Differential runtime, semantic, CLI, fixpoint and reclamation checks.

Never generates expectations. lli executes only bounded fixtures; potentially
nonterminating examples are inspected structurally instead of being run.
"""
import contextlib
import gc
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import weakref

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.compiler import (
    Parser, SemanticChecker, CodeGen, CompileError, FunctionNode, lex, main,
    compile_tree,
)
from src.optimization import EffectAnalysis, UseCounter, UnusedRemover, remove_unused
import llvmlite.binding as llvm


def checked(source):
    tree = Parser(lex(source.encode())).parse_program()
    SemanticChecker().visit(tree)
    return tree


def dump(tree):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        tree.dump()
    return stream.getvalue()


def emit(tree):
    text = str(CodeGen().visit(tree))
    verified = llvm.parse_assembly(text)
    verified.verify()
    for function in verified.functions:
        for block in function.blocks:
            for instruction in block.instructions:
                if instruction.opcode == 'alloca':
                    assert block.name == 'entry', function.name
    return text


def invoke(args):
    saved = sys.argv
    sys.argv = ['compiler.py'] + args
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main()
    finally:
        sys.argv = saved
    return status, out.getvalue(), err.getvalue()


fixtures = sorted(Path('tests/opt').glob('*.txt'))
assert len(fixtures) >= 6
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / 'program.ll'
    for path in fixtures:
        expected = path.with_suffix('.expected').read_text()
        data = path.with_suffix('.in').read_bytes() if path.with_suffix('.in').exists() else b''
        for optimize in (False, True):
            tree = checked(path.read_text())
            if optimize:
                remove_unused(tree)
                ast = dump(tree)
                assert ast == path.with_suffix('.astc').read_text(), path
                remove_unused(tree)
                assert dump(tree) == ast, ('not idempotent', path)
            output.write_text(emit(tree))
            result = subprocess.run(['lli', str(output)], input=data, capture_output=True, timeout=10)
            assert result.returncode == 0 and not result.stderr, (path, result)
            assert result.stdout.decode() == expected, (path, optimize, result.stdout)
        # Optimization must be deterministic for Windows line endings too.
        windows = checked(path.read_text().replace('\n', '\r\n'))
        remove_unused(windows)
        assert dump(windows) == path.with_suffix('.astc').read_text(), path

    source = 'tests/opt/warmup_chain.txt'
    expected = Path(source).with_suffix('.astc').read_text()
    flag = '--remove-unused'
    mode = '--ast-checked'
    for args in (
        [flag, source, str(output)], [source, flag, str(output)], [source, str(output), flag],
    ):
        assert invoke(args) == (0, '', ''), args
        assert '%"x" = alloca' not in output.read_text()
        llvm.parse_assembly(output.read_text()).verify()
    for args in (
        [flag, mode, source], [mode, flag, source], [mode, source, flag],
        [source, flag, mode], [source, mode, flag], [flag, source, mode],
    ):
        assert invoke(args) == (0, expected, ''), args
    for mode in ('--ast', '--tokens'):
        baseline = invoke([mode, source])
        assert baseline[0] == 0
        assert invoke([source, flag, mode]) == baseline
    for args in ([flag], [flag, '--unknown', source], [flag, '--ast', '--tokens', source]):
        assert invoke(args)[0] == 1, args

    invalid = Path(directory) / 'invalid.txt'
    invalid.write_text('i32 unused{missing}\nexit 0\n')
    output.write_text('stale previous output')
    with patch('src.optimization.remove_unused', side_effect=AssertionError('optimized invalid tree')):
        status, out, err = invoke([str(invalid), flag, str(output)])
    assert status == 1 and not out and 'line 1:12' in err
    assert not output.exists()

# All previous valid programs remain valid LLVM after optimization. Full lli
# behavior and exact diagnostics in both modes are exercised by run_tests.sh.
for path in sorted(Path('tests/ok').glob('*.txt')) + sorted(Path('tests').glob('valid*.txt')):
    tree = checked(path.read_text())
    remove_unused(tree)
    emit(tree)
for path in sorted(Path('tests/err').glob('*.txt')) + sorted(Path('tests').glob('invalid*.txt')):
    expected = path.with_suffix('.expected' if path.parent.name == 'err' else '.err').read_text()
    try:
        tree = checked(path.read_text())
        remove_unused(tree)
    except CompileError as error:
        assert f'compilation error: {error}\n' == expected, path
    else:
        raise AssertionError(('invalid accepted', path))

# Handwritten goldens independent of snapshot authoring.
assert dump(remove_unused(checked(Path('tests/opt/warmup_chain.txt').read_text()))) == (
    'Program\n  Decl z i32 const\n    Const 15\n  Exit\n    Var z\n'
)
assert dump(remove_unused(checked(Path('tests/opt/warmup_shadow.txt').read_text()))) == (
    'Program\n  Decl r i32 mut\n    Const 0\n  If\n    Bool true\n    Block\n'
    '      Decl x i32 const\n        Const 10\n      Assign r\n        Var x\n'
    '  Exit\n    Var r\n'
)
expected_rounds = {
    'warmup_chain': [(1, 0), (1, 0), (0, 0)],
    'warmup_shadow': [(1, 0), (0, 0)],
    'function_chain': [(0, 1), (0, 1), (0, 0)],
    'bonus_pure': [(2, 0), (0, 1), (0, 1), (0, 0)],
    'nothing_removed': [(0, 0)],
}
for name, expected in expected_rounds.items():
    optimizer = UnusedRemover()
    tree = checked(Path(f'tests/opt/{name}.txt').read_text())
    optimizer.run(tree)
    assert optimizer.rounds == expected, (name, optimizer.rounds)

tree = checked(Path('tests/opt/warmup_shadow.txt').read_text())
counter = UseCounter()
counter.visit(tree)
outer = tree.statements[1]
inner = tree.statements[2].then_block.statements[0]
assert outer.name == inner.name == 'x' and outer is not inner
assert counter.reads[id(outer)] == 0 and counter.reads[id(inner)] == 1

# Task 1 alone keeps every call. Bonus removes only provably quiet calls.
tree = checked(Path('tests/opt/bonus_pure.txt').read_text())
conservative = UnusedRemover(analyze_effects=False)
conservative.run(tree)
assert conservative.rounds == [(0, 0)]
assert all(f'Decl {name} ' in dump(tree) for name in ('a', 'b', 'c'))
functions = {node.name: node for node in tree.statements if type(node) is FunctionNode}
effects = EffectAnalysis(tree)
assert functions['loud'] in effects.effectful
assert functions['square'] not in effects.effectful
assert functions['quiet'] not in effects.effectful

chain = remove_unused(checked(Path('tests/opt/function_chain.txt').read_text()))
text = emit(chain)
defined = [f.name for f in llvm.parse_assembly(text).functions if not f.is_declaration]
assert set(defined) == {'main', 'user.twice'}, defined
assert not remove_unused(checked(Path('tests/opt/removed_lambda_registry.txt').read_text())).generated_structs

# A recursive cycle is effectful; so is a caller outside the cycle. No execution
# of the deliberately nonterminating call below is attempted.
cyclic_source = (
    'fn caller := () -> i32\n{\n exit left()\n}\n'
    'fn left := () -> i32\n{\n exit right()\n}\n'
    'fn right := () -> i32\n{\n exit left()\n}\n'
    'i32 kept{caller()}\nexit 0\n'
)
cyclic = checked(cyclic_source)
effects = EffectAnalysis(cyclic)
assert all(f in effects.effectful for f in cyclic.statements if type(f) is FunctionNode)
assert 'Decl kept' in dump(remove_unused(cyclic))

# Compiler API follows the same route and never invokes LLVM's opt.
api_tree = Parser(lex(b'i32 unused{1}\nexit 0\n')).parse_program()
assert '%"unused" = alloca' not in str(compile_tree(api_tree, optimize=True))

# Do not retain a strong local reference to the victim or the counting table.
memory_tree = checked('i32 unused{42}\nexit 0\n')
reference = weakref.ref(memory_tree.statements[0])
remove_unused(memory_tree)
immediate = reference() is None
gc.collect()
assert reference() is None
print(f'Removed DeclNode weakref: before gc = {None if immediate else "alive"}, after gc = None')
print(f'Practice 9: {len(fixtures)} dual-mode runtime fixtures, prior IR/errors, flags, effects, rounds and memory PASS')
