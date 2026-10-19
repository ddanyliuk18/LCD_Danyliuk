Implements Practice 7 member functions and the additional struct call-chain task.
Methods receive object pointers, resolve locals before fields and members before
globals, and propagate mutation through cyclic member calls before checking
receiver mutability. Adds reserved read()/print, byte literals, recursive struct
printing, and temporary-copy member chains.

Validation: 142 checks pass with zero failures, including all previous fixtures,
16 new valid and 32 new invalid programs, full stdout with .in stdin, exact AST
and diagnostics, LLVM verification, entry allocations, LF/CRLF and mem2reg.
Combined line/branch coverage is 95%. Teacher demo produces 83 for Task 1,
required Task 3 output with input 3 4, and 46 for the bonus; Point_shift has a
pointer receiver and GEP/load/add/store.

Commits separate implementation, compatibility/name fixes, tests, and docs.
The supplied assignment specifies no numeric commit minimum. README, grammar,
ai_usage.txt and docs/verification.md describe behavior and measured checks.
Run bash tools/demo_practice7.sh for the teacher presentation.

Dependency: builds on Practice 6 in #5, which is still open. The required target
is main, so this PR currently includes that foundation. Merge #5 first to reduce
the displayed diff to the Practice 7 continuation; do not merge this PR merely
to submit it for teacher review.
