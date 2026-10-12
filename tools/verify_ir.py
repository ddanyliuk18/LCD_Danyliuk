"""Check LLVM structure, repeat compilation and Windows line endings."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.compiler import Parser, SemanticChecker, CodeGen, CompileError, lex, main
import llvmlite.binding as llvm


def compile_source(data):
    tree = Parser(lex(data)).parse_program()
    SemanticChecker().visit(tree)
    module = CodeGen().visit(tree)
    text = str(module)
    checked = llvm.parse_assembly(text)
    checked.verify()
    for function in checked.functions:
        for block in function.blocks:
            for instruction in block.instructions:
                if instruction.opcode == 'alloca':
                    assert block.name == 'entry', (function.name, block.name)
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        tree.dump()
    return text, stream.getvalue()


valid_sources = sorted(Path('tests/ok').glob('*.txt')) + sorted(Path('tests').glob('valid*.txt'))
for source in valid_sources:
    data = source.read_bytes().replace(b'\r\n', b'\n')
    text, ast = compile_source(data)
    windows_text, windows_ast = compile_source(data.replace(b'\n', b'\r\n'))
    assert text == windows_text and ast == windows_ast, source
    assert ast == source.with_suffix('.ast').read_text(), source
invalid_sources = sorted(Path('tests/err').glob('*.txt')) + sorted(Path('tests').glob('invalid*.txt'))
for source in invalid_sources:
    expected = source.with_suffix('.expected' if source.parent.name == 'err' else '.err').read_text()
    for data in (source.read_bytes().replace(b'\r\n', b'\n'), source.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
        try:
            compile_source(data)
        except CompileError as error:
            assert f'compilation error: {error}\n' == expected, source
        else:
            raise AssertionError(f'accepted invalid source: {source}')
text, _ = compile_source(Path('tests/ok/p6_task3.txt').read_bytes())
for required in ('%"Point" = type {i32, i32}', 'getelementptr', 'define i32 @"user.add"', 'call i32 @"user.add"'):
    assert required in text, required
text, _ = compile_source(Path('tests/ok/p6_additional.txt').read_bytes())
assert 'insertvalue' in text
text, _ = compile_source(Path('tests/ok/phi_both_arms.txt').read_bytes())
Path('phi-check.ll').write_text(text)
original_argv = sys.argv
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / 'output.ll'
    cases = [
        (['compiler.py'], 1),
        (['compiler.py', '--unknown', 'tests/ok/p6_task3.txt'], 1),
        (['compiler.py', '--tokens', 'tests/ok/p6_task3.txt'], 0),
        (['compiler.py', '--ast', 'tests/ok/p6_task3.txt'], 0),
        (['compiler.py', 'tests/ok/p6_task3.txt', str(output)], 0),
        (['compiler.py', 'tests/err/p6_unknown_field.txt', str(output)], 1),
        (['compiler.py', '--ast', 'tests/err/p6_unknown_field.txt'], 1),
    ]
    try:
        for argv, expected_status in cases:
            sys.argv = argv
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                assert main() == expected_status, argv
            if argv[1:2] == ['--tokens']:
                assert "'struct'\tkeyword\t1:1" in stdout.getvalue()
            if argv[1:2] == ['--ast'] and expected_status == 0:
                assert stdout.getvalue() == Path(argv[2]).with_suffix('.ast').read_text()
            if len(argv) == 3 and argv[2] == str(output):
                if expected_status:
                    assert not output.exists(), 'stale IR survived a compilation error'
                    assert stderr.getvalue() == Path(argv[1]).with_suffix('.expected').read_text()
                else:
                    assert output.exists()
                    llvm.parse_assembly(output.read_text()).verify()
    finally:
        sys.argv = original_argv
print('IR verification, entry allocas, repeated compilation, all valid CRLF and AST checks passed')
