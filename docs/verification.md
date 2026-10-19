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
