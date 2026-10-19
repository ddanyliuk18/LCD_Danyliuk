"""Record AST/diagnostic snapshots for review; never run from the test runner."""
import subprocess
import sys
from pathlib import Path

for path in sorted(Path('tests/ok').glob('p6_*.txt')):
    result = subprocess.run([sys.executable, 'compiler.py', '--ast', str(path)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    path.with_suffix('.ast').write_text(result.stdout)
for path in sorted(Path('tests/err').glob('p6_*.txt')):
    result = subprocess.run([sys.executable, 'compiler.py', '--ast', str(path)], capture_output=True, text=True)
    if not result.returncode or not result.stderr.startswith('compilation error: line '):
        raise RuntimeError(f'{path}: unexpected result {result}')
    print(f'{path.name}: {result.stderr.strip()}')
    path.with_suffix('.expected').write_text(result.stderr)
