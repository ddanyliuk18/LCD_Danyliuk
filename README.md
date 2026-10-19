# Languages and Compilers Design — Practice 7

The compiler extends Practice 6 with member functions, `read()`, `print`, and
calls in the middle of a field/member chain (the additional task).
Implementation: `src/compiler.py`; root `compiler.py` preserves the CLI.

```sh
python3 -m pip install -r requirements.txt
python3 compiler.py --ast tests/ok/p7_task1.txt
python3 compiler.py tests/ok/p7_task1.txt output.ll
lli output.ll
bash run_tests.sh
bash tools/demo_practice7.sh
```

Python 3.12 and LLVM 18 (`lli`, `opt`) are used for verification.
IR is constructed exclusively with `llvmlite.ir` and serialized with
`str(module)`. LLVM binding parsing is used only by verification tools.

Struct fields precede member functions. Methods resolve parameters and locals
before fields, and methods of their own struct before global functions. Function
bodies cannot access top-level variables. Signatures are collected before bodies.
Duplicate fields/methods and invalid declaration order report line:column.

A member receives an unnamed object pointer (`this` in LLVM). `Point_shift`
contains GEP, load, add and store on that pointer. Global functions retain the
`user.` namespace; ambiguous struct/member underscore combinations receive unique
LLVM symbols without changing source lookup.

Mutation analysis first checks every body, records direct writes and calls on
this object or its fields, then propagates mutation until no new method changes.
Mutating calls require every link of the original object's path to be `mut`.
Local shadowing does not mark a method mutating. Cyclic calls are supported.
Ordinary function parameters remain immutable independent value copies.

Struct-valued call results are temporary copies. Their fields use `extractvalue`;
a method call stores the result in an entry-block alloca and passes its address.
Mutating a temporary (including a nested const field of the copy) is allowed;
assignment to any call result is rejected. The original object stays unchanged.

`read()` reads an i32 through scanf and an entry-block slot. `print(value)` is a
statement available in every statement context. It prints i32, i64, true/false,
literal byte text, and recursively formatted structures in declaration order.
Literal text uses `%s`, preserving percent signs and literal backslashes. Strings
are allowed only directly inside print and cannot span lines. `read` and `print`
are reserved for variables, parameters, fields and function/member names.

Earlier arithmetic, booleans, branching, loops, nested initializers, copies,
function recursion, widening and mutability rules remain supported. Programs
still declare structs, global functions, statements, then a final `exit` factor.
Standalone calls, grouping parentheses and unary minus remain unsupported.

The runner checks complete stdout (including print lines and the exit line),
exact AST snapshots and exact error diagnostics, plus absence of stale IR after
errors. A source with input has a neighboring `.in` file passed to lli's stdin;
other programs receive /dev/null. Structural checks verify LLVM modules, entry
allocations, repeated compilations, LF/CRLF, pointer receivers, scanf/printf,
GEP/load/add/store and bonus extractvalue; mem2reg must produce a phi.

Practice 7 adds 16 positive and 32 negative fixtures. Runtime expectations are
specified independently in the authoring helper; the test runner never creates
expectations. Previous Practice 2–6 fixtures remain intact. See
`docs/verification.md` for measured results and `ai_usage.txt` for assistance.

Submission uses branch `practice-7`, a PR into `main`, and reviewer
`vovaskochko`. The assignment specifies no numeric minimum or exact sequence of
commits; implementation, compatibility fixes, tests and documentation have
separate commits. The demo shows Task 1 AST and result 83, Point_shift IR, two
required line:column rejections, Task 3 with input 3 4, and bonus result 46.
Show it to the teacher during practice or within the stated three-day window.
