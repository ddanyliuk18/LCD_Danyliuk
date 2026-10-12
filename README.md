# Languages and Compilers Design — Practice 6

The compiler has a typed front end and a semantic pass before LLVM code
generation:

```text
source bytes -> lexer -> parser -> AST -> SemanticChecker -> CodeGen -> LLVM IR
```

Implementation lives in `src/compiler.py`; root `compiler.py` retains the CLI.
Install dependencies with `python3 -m pip install -r requirements.txt` and
install LLVM (`lli` and `opt`) for the test and demonstration scripts.

The language supports named structs, functions, recursive/forward calls, field
chains, struct copies and nested braced initialisation, plus typed declarations, arithmetic, `==`, `!=`, unary `!`,
mutable assignment, nested `if`/`else` blocks, `while` loops, exits in blocks,
and one final program `exit`. Both LF and CRLF source files are accepted.
Blank lines are also allowed before block braces and around `else`.

Programs declare structs, then functions, then statements and a final exit.
Structs have at least one field; field types are built-ins or structs declared
earlier. A single initializer of the same struct type copies the object.
Inner braces initialise struct fields recursively and report errors at their
own opening brace. Built-in fields cannot use nested braces.

Writes require a mutable root and mutable fields along the entire path.
Replacing a whole struct additionally requires every contained field, at every
depth, to be mutable. Parameters and object copies are independent values.

Signatures are collected before function bodies. Functions see parameters,
locals and all functions, but no top-level variables. Parameters are immutable
and share a scope with the outermost body locals. Bodies end with an explicit
exit of exactly the result type; exits in branches return immediately.
Arguments and initialisation allow i32 to i64 widening. Top-level exit accepts
only built-in types. Exit still takes a factor; grouping parentheses, unary
minus and standalone call statements are unsupported.

Semantic analysis attaches numeric field indices and declaration/function
links to the AST. Code generation uses named types, GEPs, aggregate values,
insertvalue, call and ret through llvmlite.ir. User function names have the
`user.` prefix to avoid runtime main/printf collisions. Each compilation
owns an independent LLVM type context.

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
bash tools/demo_practice6.sh
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

Practice 6 adds 16 valid and 30 invalid programs: all six required scenarios
in each category, supplied examples, nested initialisers, const paths,
parameter writes, global isolation, ordering, recursion, independent copies
and runtime-name collisions. Runtime expectations are specified independently;
AST and diagnostic snapshots are checked in for exact comparison. Authoring
helpers never run during tests. Additional checks verify LLVM modules, every
alloca in entry, repeated compilation, all valid tests/ok programs with CRLF,
and a phi after mem2reg.

The demo runs Task 2 (true), Fibonacci (55), Task 3 (28), and the additional
task (36), displays the Point type, GEP, definitions and calls, and rejects
three programs with line:column. It leaves Task 3 IR in `output.ll` to inspect.
See `docs/verification.md` for results and `ai_usage.txt` for AI assistance.

Submit branch `practice-6` through a PR into `main` with `vovaskochko` as
reviewer. The supplied assignment gives no numeric commit minimum; work is
split into focused commits. Show the demo to the teacher during practice or
within three days; running the script does not replace that presentation.
