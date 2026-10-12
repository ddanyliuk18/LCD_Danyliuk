Adds named structs, typed functions, field access and calls while preserving
the previous language. Blank lines around if/else braces now compile.

The semantic pass checks declaration order, argument/result types, immutable
parameters, function-local visibility and every mutable link in field writes.
Functions support recursion and forward calls. Structs support value copies
and the additional nested initialisation task.

LLVM is generated exclusively through llvmlite.ir, using named types, GEP
indices resolved by the semantic pass, entry allocas, insertvalue, call and ret.
Implementation is in src/ with the existing root CLI preserved.

Validation includes all earlier tests, 16 new valid and 30 new invalid
programs, exact ASTs/diagnostics, lli results true/55/28/36, LLVM verification,
entry alloca checks, CRLF equivalence and mem2reg phi checks. The demo script
shows the required IR constructs and three line:column rejections.

Final runner: 94 passed, 0 failed. Combined line/branch coverage: 93%.
Eight focused commits cover the review fix, implementation, tests, cleanup,
validation and documentation.

See docs/verification.md for the final test/coverage results and ai_usage.txt
for the Practice 6 assistance record.
