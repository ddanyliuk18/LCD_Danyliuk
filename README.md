# Languages and Compilers Design — Practice 5

The compiler has a typed front end and a semantic pass before LLVM code
generation:

```text
source bytes -> lexer -> parser -> AST -> SemanticChecker -> CodeGen -> LLVM IR
```

The language supports typed declarations, arithmetic, `==`, `!=`, unary `!`,
mutable assignment, nested `if`/`else` blocks, `while` loops, exits in blocks,
and one final program `exit`. Both LF and CRLF source files are accepted.

`SemanticChecker` owns a stack of scope frames and resolves uses to the nearest
declaration. `CodeGen` emits real then/else/merge basic blocks and keeps every
`alloca` in the entry block for `opt -passes=mem2reg`. A while loop uses
condition/body/end blocks and a back edge from its body to its condition. LLVM
IR is built only with `llvmlite.ir` and written only with `str(module)`.

## Interface

```bash
python3 compiler.py input.txt output.ll
python3 compiler.py --ast input.txt
lli output.ll
```

For example:

```bash
python3 compiler.py tests/ok/if_without_else.txt output.ll
lli output.ll
# Program exit with result 15

python3 compiler.py tests/ok/if-else_nested.txt output.ll
lli output.ll
# Program exit with result 20

python3 compiler.py tests/ok/phi_both_arms.txt output.ll
opt -passes=mem2reg -S output.ll
```

The AST declaration line includes the declared type, for example
`Decl y i64 mut`. On every lexical, syntax, or semantic error the compiler
prints one `compilation error: line:column: ...` diagnostic, exits non-zero,
and leaves no output file.

## Tests

```bash
bash run_tests.sh
```

The runner keeps all Practice 2–4 regression tests and checks the new
`tests/ok` and `tests/err` suites. Valid cases compare runtime output and exact
AST snapshots. Invalid cases compare exact diagnostics and ensure that no IR
file was written. It also converts a valid program to CRLF and checks that the
Windows-line-ending version produces the same AST.

The Practice 5 cases cover optional and present `else`, nested branches,
different-type shadowing, exit inside an arm, `!`, assignments in both arms,
block lifetime, same-frame redeclaration, condition types, brace placement,
empty/unclosed blocks, and statements after a block exit.
The additional while case sums the integers from 1 through 10 and prints 55;
an error case checks that a while condition must be bool.
