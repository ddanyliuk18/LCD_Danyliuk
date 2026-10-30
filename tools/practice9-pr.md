Adds --remove-unused to remove unread variable declarations and their writes,
then uncalled global functions, repeatedly until nothing changes. Reads are
counted per resolved declaration identity, preserving shadowing. The flag works
anywhere, runs only after semantic acceptance and affects --ast-checked while
--ast retains the parse tree. Parameters, fields, members and lambdas stay.

Includes the additional task: resolved call-graph effect analysis preserves
print/read, mutating calls and possible nontermination (while and recursive
cycles), then propagates effects to callers. Pure unused calls can disappear
and expose further uncalled functions. Nested argument effects and lambda
capture/call semantics are covered; orphan generated closure registry entries
are removed with an enclosing global.

The pass operates solely on the tree. It never invokes LLVM opt; all IR
construction remains llvmlite.ir with str(module) serialization.

Validation:

- Full suite without and with the flag: **189 passed, 0 failed in each mode**;
  the environment-variable runner mode was also exercised.
- **29 tests/opt programs**, each with .astc and independent full stdout;
  all run through lli both ways (58 executions), including all six mandatory
  cases and bonus cases for pure calls, mutation, propagation, loops, recursion,
  printing/quiet lambdas, input and mut captures.
- Earlier fixtures unchanged; exact stdout/errors, LLVM verification, LF/CRLF,
  entry allocas, mem2reg, flag positions, invalid-before-pass, exact round counts,
  shadowing and optimizer idempotence pass.
- Combined line/branch coverage: **96% overall, 99% optimizer**; optimizer
  statement coverage is 100%.
- Actual removed-node weakref is None before and after gc.collect(). The
  required memory/self-feeding/cycle note is under Optimizations in README.
- The demo verifies warm-up trees, result 4 with only twice/main definitions,
  and bonus output 5 with exit 0. Use bash tools/demo_practice9.sh --full for
  the teacher. The student must still personally show the demonstration.

Six focused commits cover implementation, fixtures, verification, added effect
boundaries, documentation and final evidence. ai_usage.txt quotes the full
literal prompt and separates accepted output from changes. A Ukrainian
walkthrough explains all implementation decisions and limits.

Dependency: Practice 8 PR #7 is still open. This continues that compiler on the
required main base; merge #7 before this PR to narrow the diff to Practice 9.
