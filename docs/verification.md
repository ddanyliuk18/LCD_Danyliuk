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
