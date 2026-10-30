# Practice 6 verification

Environment: Ubuntu WSL, Python 3.12, llvmlite 0.50.0, LLVM 18,
coverage.py 7.16.2. Verification performed on 2026-10-12/13 local time.

## Runtime and submission demonstration

`bash tools/demo_practice6.sh` ran through `lli`:

| Program | Output result |
|---|---|
| Task 2 check | true |
| Recursive Fibonacci | 55 |
| Task 3 structs and calls | 28 |
| Additional nested initialisation | 36 |

The Task 3 `output.ll` contains `%"Point" = type {i32, i32}`, GEPs with
numeric indices, user function definitions and calls. The additional program
uses insertvalue to construct nested struct values. User functions are named
`user.add`, `user.isXZero`, etc. to protect runtime names.

The demonstration rejected these programs with the expected source locations:

| Test | Location | Reason |
|---|---|---|
| p6_unknown_field | 7:8 | Point has no field z |
| p6_const_link | 13:3 | center is const |
| p6_return_type | 3:2 | bool function exits with i32 |

## Checks

Final `bash run_tests.sh`: **94 passed, 0 failed**. `git diff --check` passed.

The suite preserves the original 46 checks and adds the blank-line regression,
16 Practice 6 valid programs, 30 invalid programs and one comprehensive LLVM
structure check. Runtime expectations are independently specified. The runner
compares exact ASTs and diagnostics and checks that erroneous compilation does
not leave IR. Snapshot authoring scripts never run from the verification suite.

`tools/verify_ir.py` additionally checks every valid source and error fixture
in both LF and CRLF form; valid modules pass LLVM verification, every alloca
belongs to its function's entry block, and repeated compilation creates no
named-type context collisions. It tests CLI usage, AST/tokens, generated IR
and deletion of a previous successful IR file when the next compilation fails.
The runner invokes `opt -passes=mem2reg` and asserts an i32 phi exists.

Coverage command (with coverage installed):

```bash
python3 -m coverage run --branch --source=src tools/verify_ir.py
python3 -m coverage report -m
```

Measured: 1,072 executable statements, 50 uncovered statements, 410 branches,
39 partially covered branches; combined line/branch coverage is 93%.
This measures the in-process frontend/IR/CLI checks. Runtime tests through lli
are additional validation and are not included in that coverage measurement.

No numeric coverage or commit minimum is specified in the provided assignment.
The implementation includes more than six tests in each required directory and
is organized into focused commits. All compiler IR is constructed through
llvmlite.ir and serialized only with str(module); parse_assembly is used only
by this verification code.

The teacher presentation remains a student action. Run the demo during the
practice or within the assignment's three-day deadline.

## Practice 7 verification (2026-10-19)

Environment: Ubuntu WSL, Python 3.12, llvmlite 0.50.0, LLVM 18.
Dependencies were loaded from /var/tmp/lcd-practice6-deps with PYTHONPATH.

Final independent full run:

```text
bash run_tests.sh
Passed: 142
Failed: 0
```

Includes 16 new valid and 32 new invalid Practice 7 programs; all earlier
fixtures remain unchanged. Every valid case runs through lli, compares complete
stdout and exact AST, and is additionally verified as LLVM IR with entry-block
allocas. Invalid cases compare exact diagnostics, including line:column, and
ensure no output file survives. Input comes from .in files. Valid and invalid
front-end checks are repeated with CRLF. mem2reg still produces a phi.

```text
python3 -m coverage run --branch --source=src tools/verify_ir.py
python3 -m coverage report -m
src/compiler.py: 1320 statements, 52 missed, 532 branches, 40 partial, 95%
```

Coverage measures the in-process compiler/IR/CLI suite. Separate lli runtime
comparisons validate printed output and scanf input. Coverage is reported as
combined line/branch coverage; the assignment gives no numeric threshold.

The teacher demo is `bash tools/demo_practice7.sh`. It shows the Task 1 AST
and result 83, Point_shift with a pointer first argument and GEP/load/add/store,
field-after-method rejection at 8:2, const-object mutation rejection at 31:6,
Task 3 with input 3 4 and all expected output lines, and bonus result 46.
The structural checker asserts the receiver pointer and required instructions,
a single printf/scanf declaration, temporary storage and extractvalue.

Additional tests cover two-argument calls, implicit member lookup, indirect and
cyclic mutation propagation, local/parameter shadowing, global/member precedence,
underscore symbol collisions, prints in loops/branches/functions/members,
negative integers, i64, bool, percent/backslash literals, nested structures,
struct call results, and mutations of temporary nested fields without changing
the original. Negative cases cover declaration order/duplicates, isolation,
const paths/fields, argument/return types, scalar/type calls, reserved names,
invalid strings/print/read uses, standalone calls and assignment to temporaries.

Commit sequence for this practice:
1. f8874b5 — member functions, mutation analysis, built-ins and bonus chains.
2. 78243aa — Practice 6 compatibility and ambiguous member symbol names.
3. 07b18f4 — fixtures, stdin runner, LLVM invariants and demonstration script.
4. Documentation — grammar, usage, AI disclosure and measured verification.

An early overlapping runner invocation produced temporary-file interference;
its results were discarded. Real diagnostic/GEP regressions were corrected,
then the complete runner passed alone. No legacy fixtures were rewritten to
hide differences. IR construction is entirely llvmlite.ir; only validation uses
binding parse_assembly. The teacher presentation is still the student's action.

Submission dependency: Practice 6 PR #5 was still open when Practice 7 PR #6
was created against the required main branch. The PR description identifies
this dependency. Merging #5 first will narrow #6 to the Practice 7 changes.
A final documentation commit records this verified submission relationship.

## Practice 8 verification (2026-10-30)

Environment: Ubuntu WSL, Python 3.12, llvmlite 0.50, LLVM 18 lli/opt,
coverage.py 7.16.2. Existing dependencies were used with
`export PYTHONPATH=/var/tmp/lcd-practice6-deps`.

Final complete run, after all compiler and fixture changes:

```text
bash run_tests.sh
Passed: 188
Failed: 0
```

The 142 earlier checks remain; Practice 8 adds 15 valid and 31 invalid programs.
Every valid program is compiled and executed through lli with its neighboring
`.in` file or /dev/null, comparing complete stdout and parse AST snapshots.
All 15 Practice 8 cases also compare `--ast-checked` snapshots. Invalid cases
compare exact diagnostics with line:column and assert no IR file survives.
Earlier source, stdout, AST and error fixtures were not changed.

`tools/verify_ir.py` repeats valid and invalid compilation with LF/CRLF and
verifies every LLVM module, entry-block allocas, repeated compilation and CLI
behavior. `tools/verify_practice8.py` independently checks real MemberCallNode
lowering, byte-for-byte LLVM equivalence of short and explicit calls, lambda
type/function/receiver signatures, capture GEP/store order, nested closure
copies, mutable closure declarations and generated method mutation, checked
AST snapshots and the new CLI flag on valid/invalid input. opt mem2reg still
produces the required phi. IR construction remains entirely llvmlite.ir;
parse_assembly is verification only.

Coverage was measured after the complete runtime suite, sequentially to avoid
shared temporary-file interference:

```sh
python3 -m coverage run --branch --source=src tools/verify_ir.py
python3 -m coverage run --append --branch --source=src tools/verify_practice8.py
python3 -m coverage report -m
```

```text
Name              Stmts   Miss Branch BrPart  Cover
src/compiler.py    1511     52    620     42    95%
TOTAL              1511     52    620     42    95%
```

95% is combined line/branch coverage; 1459 of 1511 statements are covered.
Separate lli executions validate observable runtime behavior and are not part
of that in-process coverage measurement. No numeric coverage threshold or
commit minimum appears in the supplied assignment.

`bash tools/demo_practice8.sh` completed successfully and compared full output:

| Example | Print lines | Exit result |
|---|---|---|
| Task 1 | 42, 42, 14, 10, Counter{n: 2} | 12 |
| Task 2 | 15, 100, 50 | 11 |
| Additional mut captures | 1, 2, 34, 3 | 0 |

The demo also showed the Task 2 checked AST, `%"lambda.add_k" = type {i32}`
and `lambda.add_k_call` with its object pointer and parameter, GEP/load/add.
It rejected missing capture at 4:8, lambda passed to sq at 12:9 and mutating
call through a const captured closure at 11:8. Locations correspond to the
repository fixtures, whose indentation differs from the assignment PDF.

Coverage includes callable fields and implicit self fields, short/explicit
calls, signature failures, variable/function ambiguity, const receiver paths,
empty captures with global calls, declaration-time copies, parameter and field
captures, nested/loop/if lambdas, capturing another closure, unnamed-type
restrictions, hidden captures, duplicate/unknown/conflicting captures, missing
captures, no self-recursion, invalid nested functions/member capture lists,
generated-call isolation, repeated source names in separate scopes, i64/bool,
read input, independent mutable copies, mixed const/mut captures and const
struct fields inside mut captures.

Five meaningful Practice 8 commits separate compiler implementation, runtime
fixtures, independent structural verification/demo, grammar/README and the
final measured evidence/AI disclosure. The literal user prompt and explicit
as-is/change record are in `ai_usage.txt`. The original Practice 7 disclosure
is archived without inventing an unavailable original Practice 7 prompt.

Submission targets `practice-8` -> `main` with reviewer `vovaskochko`.
Practice 6 PR #5 and Practice 7 PR #6 were still open during this submission;
the new PR explicitly identifies that ancestry. Do not merge older work as
part of this task. The teacher presentation remains the student's action,
due 30 October 2026 at 23:59 Europe/Kyiv.

## Practice 9 verification (2026-10-30)

Environment: Ubuntu WSL, CPython 3.12, llvmlite 0.50, LLVM 18 and coverage.py.
Dependencies: `export PYTHONPATH=/var/tmp/lcd-practice6-deps`.

Both complete test modes passed:

```text
bash run_tests.sh
Passed: 189
Failed: 0

bash run_tests.sh --remove-unused
Passed: 189
Failed: 0
```

The final rerun also exercised the equivalent environment-variable interface:
`REMOVE_UNUSED=1 bash run_tests.sh`, with the same 189/0 result.
Every earlier valid program runs through lli with complete stdout comparison;
every earlier invalid program retains its exact line:column diagnostic and
leaves no output IR. No earlier source/AST/error/output fixture was changed.
Original parse ASTs remain identical with the flag. Previous checked snapshots
are compared without optimization; optimized snapshots are checked for the new
optimization fixtures. Earlier LLVM and mem2reg assertions still pass.

The suite's 189 checks include one new verification group, not just one new
test program: `tools/verify_practice9.py` checks **29 tests/opt programs**, each
compiled and executed with and without optimization (**58 lli executions**).
Every optimized tree is compared with `.astc`, every execution with the full
independently specified `.expected`, and stdin comes from neighboring `.in`.
The helper also checks optimized versions of every earlier valid module and
earlier error fixture in process. Source and snapshots are deterministic under
LF/CRLF. Optimization is idempotent. Every emitted module passes LLVM verification
and every alloca remains in its entry block.

The initial 26-fixture suite passed both modes before three further effect
boundary cases were added: read inside a function, a printing lambda declared
without executing it, and an unused mut-capture call whose mutation remains
observable. All 29 then passed the independent verifier and final full rerun.

Independent checks additionally assert:

- handwritten warm-up trees, distinct declaration identities for shadowed x,
  and exact removal counts per round (including the final no-change round);
- no assignment target counts as a read; dead scalar/field writes vanish;
  effectful assignment values keep their destination declaration;
- parameters, fields, methods and lambdas remain; ordinary variables are
  processed inside functions, members, lambdas, if/else and while;
- the three-function chain defines exactly user.twice and main;
- removing a global also removes its orphan lambda registry entries;
- every placement of --remove-unused relative to paths and checked-AST mode;
  parse/token modes stay unchanged; malformed arguments retain usage errors;
- a patched optimizer is never invoked on a semantically invalid program,
  including an unused declaration with an unknown name; stale IR is removed;
- basic Task 1 retains all call initializers when analyze_effects=False;
  bonus mode removes pure calls and their subsequently uncalled functions;
- print/read/mutation, nested argument/struct-initializer effects, transitive
  effect propagation, while and direct/mutual recursion remain effectful;
- callable objects and generated lambda methods follow the same resolved graph;
  declaring a lambda does not execute its body;
- self-feeding variables and mutually called globals survive as required limits.

Potentially nonterminating call graphs are inspected structurally rather than
executed. Runtime recursive/loop examples are bounded, and lli has a timeout.
Fixture authoring never runs from the verification suite.

### Coverage

```sh
python3 -m coverage run --branch --source=src tools/verify_ir.py
python3 -m coverage run --append --branch --source=src tools/verify_practice8.py
python3 -m coverage run --append --branch --source=src tools/verify_practice9.py
python3 -m coverage report -m
```

```text
Name                  Stmts   Miss Branch BrPart  Cover
src/compiler.py        1524     50    624     43    95%
src/optimization.py     129      0     72      1    99%
TOTAL                  1653     50    696     44    96%
```

These are combined line/branch percentages; the new optimization module has
100% statement coverage. The single partial optimizer branch is the generic
execution walker stopping on a function/struct root; production analysis starts
from bodies/expressions. Separate lli processes validate runtime behavior and
are not included in in-process compiler coverage. No numeric commit/coverage
minimum is present in the supplied assignment.

### Memory and demonstration

The verifier took a weakref to the declaration in `i32 unused{42}; exit 0`,
without another strong local reference. Actual observation:

```text
Removed DeclNode weakref: before gc = None, after gc = None
```

The reference is asserted to be None after gc.collect; the reported immediate
None shows this node was already reclaimed by CPython reference counting.
README's Optimizations section explains reference counting, cyclic GC, absence
of a generic parent pointer, semantic back-links, strong-parent cycles and the
difference between compiler memory and the compiled language's absent heap.

`bash tools/demo_practice9.sh` completed successfully:

| Demonstration | Verified observation |
|---|---|
| First warm-up | only z and exit z; result 15 in runtime fixtures |
| Shadowing warm-up | outer x removed; inner x and r assignment remain; result 10 |
| Three-function chain | result 4; definitions exactly main and user.twice |
| Bonus pure calls | only loud, c and exit remain; prints 5; result 0 |
| Memory | weakref None before and after explicit cyclic GC |

The demo prints both optimized warm-up trees, definitions, bonus tree/output,
the verifier and README note. `bash tools/demo_practice9.sh --full` also runs
both complete suite modes for the teacher.

Six meaningful Practice 9 commits separate implementation, 26 initial fixtures,
independent verification/runner/demo, three further effect-boundary regressions,
documentation/AI disclosure and final evidence/submission body. The literal
task message and explicit as-is/change record are in ai_usage.txt; earlier
disclosures are archived. A Ukrainian walkthrough is in
docs/practice9-explained.md.

Submission: practice-9 -> main, reviewer vovaskochko. Practice 8 PR #7 was still
open during preparation and is identified as the dependency in the new PR;
the preceding Practice 6/7 PRs were no longer open. The student must personally
show the demonstration by 6 November 2026, 23:59 Europe/Kyiv.
