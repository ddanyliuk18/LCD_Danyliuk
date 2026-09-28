# Languages and Compilers Design — Practice 4

The compiler now has a typed front end and a semantic pass before LLVM code
generation:

```text
source bytes -> lexer -> parser -> AST -> SemanticChecker -> CodeGen -> LLVM IR
```

The language supports `i32`, `i64`, and `bool`; `true`/`false`; arithmetic;
`==` and `!=`; mutable assignment; and one final `exit`. Integer expressions
use widening only: `i32` may become `i64`, but values are never narrowed and
booleans never convert to integers.

`SemanticChecker` owns the symbol table, resolves every variable to its
declaration, computes every expression type, and rejects all semantic errors
before `CodeGen` is constructed. `CodeGen` therefore reads `node.type` and
`node.decl` from the checked tree and contains no declaration or type checks.
LLVM IR is built only with `llvmlite.ir` and written only with `str(module)`.

## Interface

```bash
python3 compiler.py input.txt output.ll
python3 compiler.py --ast input.txt
lli output.ll
```

For example:

```bash
python3 compiler.py tests/ok/task1.txt output.ll
lli output.ll
# Program exit with result 385

python3 compiler.py tests/ok/bool_exit.txt output.ll
lli output.ll
# Program exit with result true
```

The AST declaration line includes the declared type, for example
`Decl y i64 mut`. On every lexical, syntax, or semantic error the compiler
prints one `compilation error: line:column: ...` diagnostic, exits non-zero,
and leaves no output file.

## Tests

```bash
bash run_tests.sh
```

The runner keeps all Practice 2/3 regression tests and checks the new
`tests/ok` and `tests/err` suites. Valid cases compare runtime output and exact
AST snapshots. Invalid cases compare exact diagnostics and ensure that no IR
file was written.

The Practice 4 cases cover widening in initialisation and arithmetic, an i64
constant, mixed-width integer comparison, boolean comparison and exit, boolean
arithmetic, both narrowing contexts, overflow, a mixed boolean/integer
comparison, and a lone `=` lexical error.
