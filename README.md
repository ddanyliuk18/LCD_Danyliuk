# Languages and Compilers Design — Practice 8

Practice 8 adds callable objects, lambdas and the additional **mut captures** task
to the Practice 7 compiler. Earlier language features and fixtures are retained.
Implementation: `src/compiler.py`; root `compiler.py` preserves the CLI.

```sh
python3 -m pip install -r requirements.txt
python3 compiler.py --ast tests/ok/p8_task2.txt
python3 compiler.py --ast-checked tests/ok/p8_task2.txt
python3 compiler.py tests/ok/p8_task2.txt output.ll
lli output.ll
bash run_tests.sh
bash tools/demo_practice8.sh
```

Verification uses Python 3.12, llvmlite 0.50 and LLVM 18 (`lli`, `opt`). In the
current WSL environment the already installed dependencies are available with
`export PYTHONPATH=/var/tmp/lcd-practice6-deps`.

A visible variable wins name lookup at a call and must have a struct type with
a `call` method. If a function with the same name is also visible, the call is
rejected; both declarations themselves are legal. A called field such as
`s.scale(7)` becomes `s.scale.call(7)`. Inside a member, `scale(side)` can call
its own field. All these forms lower to real `MemberCallNode` objects during
semantic analysis and use the existing argument and mutation checks. Short and
explicit calls produce identical LLVM IR.

`fn name := [captures](parameters) -> type` is a statement at top level or in
any block. A plain nested `fn` and captures on struct members remain errors.
Each declaration takes value copies of the captures at that point; declarations
inside loops take fresh copies every iteration. Bodies see their parameters,
locals, captures and global functions. Enclosing locals, parameters, fields and
top-level variables require explicit captures. The lambda name is bound after
checking its body. Duplicate/unknown captures and parameter/capture collisions
are rejected at their source positions.

The semantic pass creates a unique `lambda.name` struct, a `call` member and a
closure variable. Repeated names in separate scopes get numeric suffixes. The
type cannot be spelled in source code. Lambda values cannot be passed, returned,
assigned, printed or used to initialize a declared variable/field. Captures
cannot be accessed with a dot outside the lambda body. Capturing another lambda
is supported as an internal value copy.

`[mut n]` gives the closure an independent mutable copy, even when the original
variable is const. Any mut capture makes the closure variable mutable. Existing
fixed-point mutation analysis covers generated methods, including calls through
captured lambdas. `[next]` is a const copy and rejects a mutating `next()`;
`[mut next]` permits it. Original variables and other closures remain unchanged.
Normal struct field mutability still applies inside a mut capture.

`--ast` shows the parse tree (`Call`, `Lambda`, `Capture`); `--ast-checked` shows
generated structs, members, closure declarations and `CallableCall` rewrites.
Both validate the program and report semantic errors with `line:column`.
Historical typed initializer labels in parse AST snapshots are retained.
All IR construction uses `llvmlite.ir`; the sole output serialization is
`str(module)`. Closure declarations emit an entry alloca and a GEP/store per
capture. LLVM binding parsing is used only for verification.

Practice 8 adds **15 valid and 31 invalid programs**. The runner compares the
whole stdout including prints and the exit line, exact parse/checked ASTs and
exact diagnostics, and ensures errors leave no stale IR. Input comes from a
neighboring `.in` file. Earlier fixtures are unchanged. Independent structural
checks verify short/explicit IR equivalence, captured closure copies, receiver
types, declaration order, entry allocas, LF/CRLF, repeated compilation and
mem2reg. Authoring helpers are never invoked by the test runner.

See `docs/verification.md` for measured verification and coverage, and
`ai_usage.txt` for the literal user prompt and explicit acceptance/change record.
The supplied assignment gives no numeric commit minimum or coverage threshold;
implementation, fixtures, structural checks, documentation and final evidence
are recorded in separate meaningful commits.

Submission: branch `practice-8`, pull request into `main`, reviewer
`vovaskochko`. Deadline: **30 October 2026, 23:59**, Europe/Kyiv.
Run `bash tools/demo_practice8.sh` for the teacher: both required programs and
the bonus through `lli`, checked AST, `lambda.add_k` type/function and the two
required rejected programs. The student must personally show this demonstration.
