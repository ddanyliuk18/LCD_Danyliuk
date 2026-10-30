Implements callable objects, lambdas and the additional mut captures task.
`triple(14)` lowers to the same checked member call and LLVM IR as
`triple.call(14)`. Lambdas lower in semantic analysis to anonymous struct types,
call members and declaration-time capture copies, with isolated body lookup and
unnamed-type restrictions. `[mut n]` and `[mut next]` give independent mutable
copies and reuse the existing fixed-point mutation analysis.

Adds `--ast-checked`; `--ast` retains the parse tree. All IR construction stays
in llvmlite.ir, serialized only through str(module).

Validation on 2026-10-30: **188 passed, 0 failed**, including all earlier checks,
15 new valid and 31 new invalid programs, exact stdout/diagnostics, parse/checked
ASTs, input files, LF/CRLF, LLVM verification and mem2reg. In-process combined
line/branch coverage: **95%** (1511 statements, 52 missed, 620 branches,
42 partial). Independent assertions cover semantic lowering, identical IR for
short/explicit calls, capture copies, signatures and mutation propagation.

`bash tools/demo_practice8.sh` successfully reproduced both required examples
and the bonus through lli, showed the checked AST and lambda.add_k IR, and
rejected missing capture / lambda argument with line:column. The student still
needs to show that demonstration to the teacher.

`ai_usage.txt` reproduces the literal prompt and separately states what was
taken as-is and what changed. The original Practice 7 disclosure is archived.
Five focused Practice 8 commits separate implementation, fixtures, structural
checks/demo, language documentation and final evidence/disclosure. The supplied
assignment has no numeric commit minimum or coverage threshold.

Dependency: Practice 6 PR #5 and Practice 7 PR #6 are still open. This branch
continues their compiler; the required base is main. Merge those PRs in order
before this one to narrow the diff to Practice 8.
