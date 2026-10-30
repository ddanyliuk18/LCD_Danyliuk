# Languages and Compilers Design — Practice 9

The compiler adds its first tree optimization: remove unused variables and global
functions, including the additional task **calls without effects**. Practices
2–8, callable objects and mutable lambda captures remain supported.

```sh
python3 -m pip install -r requirements.txt
python3 compiler.py --remove-unused input.txt output.ll
python3 compiler.py input.txt --remove-unused output.ll
python3 compiler.py input.txt output.ll --remove-unused
python3 compiler.py --remove-unused --ast-checked input.txt
python3 compiler.py --ast input.txt --remove-unused
lli output.ll
bash run_tests.sh
bash run_tests.sh --remove-unused
# Equivalent runner selection:
REMOVE_UNUSED=1 bash run_tests.sh
bash tools/demo_practice9.sh --full
```

Verification uses Python 3.12, llvmlite 0.50, LLVM 18 lli/opt and coverage.py.
Current WSL dependencies: `export PYTHONPATH=/var/tmp/lcd-practice6-deps`.
Implementation is in `src/compiler.py` and `src/optimization.py`.
The root `compiler.py` is the compatibility entry point.

## Optimizations

The optional `--remove-unused` flag can occur anywhere. Parsing and full semantic
checking always precede optimization. `--ast` retains the parse tree;
`--ast-checked` shows the tree actually passed to code generation. Without the
flag behavior is unchanged. Invalid programs retain their diagnostics and cannot
be made valid by deleting their errors.

The counting visitor keys reads by `id(declaration)`, using the checker's `decl`
links. Different declarations named x remain different variables. Initializers,
conditions, argument values, print, exit, field/member receiver roots, callable
objects and capture copies count as reads. An assignment target does not count;
when its declaration goes, all assignments rooted in it go too. Block lists are
rebuilt without deleting from a list being traversed. Empty if/else/while blocks
remain and their conditions are still evaluated.

Each round counts both reads and calls, then removes zero-read ordinary
variables and zero-call global functions. A removal can expose another one, so
rounds repeat until a round removes nothing. Parameters, fields, member functions
and lambda declarations stay. Removing a global removes its whole body, including
any nested lambdas and their otherwise orphaned code-generation registry entries.
Lambda bodies are visited once through their generated methods, not again through
the syntax alias. Statistics retain only numeric removal counts.

The bonus builds a resolved call graph for globals, members and lambdas. Direct
print/read, a mutating method, any while, and every function on a recursive cycle
seed the effect set. Effects then propagate to callers until stable. Initializers
and assignment values with any effectful call are kept, including effects nested
in arguments or struct initializers. Pure calls can disappear, allowing their
functions to disappear in later rounds. Declaring a lambda does not execute its
body. The analysis is conservative: a while with a false condition and recursion
with a terminating argument are still treated as potentially nonterminating.
An internal `UnusedRemover(analyze_effects=False)` exercises the basic Task 1
rule that every call must be kept; the CLI enables the complete bonus behavior.

Counting has deliberate limits: `k := k + 1` reads k, so a self-feeding variable
survives even if nobody else reads it. Two globals called only by each other also
survive. This is reference/use counting, not a reachability or liveness analysis.

Memory note: this compiler is Python, verified on CPython 3.12. CPython uses
reference counting and a cyclic garbage collector. Removing a list edge releases
that reference; once the counting/pruning temporaries are gone, a node with no
remaining strong reference is reclaimed. AST nodes have no generic parent
pointer. Semantic links such as method.owner, struct.methods and recursive
call.function can form cycles; a strong parent link would likewise keep reference
counts above zero until cyclic GC collects an unreachable cycle. A removed node
still referenced elsewhere must remain alive.

Actual measurement in `tools/verify_practice9.py`: take
`weakref.ref(tree.statements[0])` for `i32 unused{42}`, run the pass, and inspect
it without retaining another strong reference. The observed result was
`before gc = None, after gc = None` (after `gc.collect()`): this declaration was
already reclaimed by reference counting. The measurement is asserted on every
verification run. This concerns the compiler's AST memory; the compiled language
has no heap, so this optimization frees no heap allocation in the binary.

The pass never invokes LLVM opt. All IR is built with `llvmlite.ir` and emitted
with `str(module)`. LLVM binding parsing and external opt/mem2reg are confined to
verification tools. The optimized three-function example defines exactly
`user.twice` and `main` and still exits with result 4.

## Tests and demonstration

`tests/opt` has 29 source programs, each with an optimized `.astc` snapshot and an
independently specified `.expected` stdout. Inputs have neighboring `.in` files.
`tools/verify_practice9.py` compiles and runs all 29 both ways through lli,
compares all output, verifies LLVM, checks LF/CRLF, idempotence, exact iteration
counts, per-declaration shadowing, flag positions, errors before optimization,
all earlier modules/errors, pure/effectful calls and weakref reclamation.
Potentially infinite recursive graphs are inspected without executing them.

The main runner supports both modes for every earlier test, including complete
stdout and unchanged error diagnostics. Parse AST snapshots remain identical;
Practice 8 checked snapshots are compared in the unoptimized run, while optimized
checked snapshots are compared for every tests/opt fixture. Independent LLVM
invariants and mem2reg remain enabled. Fixture authoring helpers never run as
part of verification. See `docs/verification.md` for measured suite/coverage
results and commands.

`bash tools/demo_practice9.sh` shows both warm-up trees, the three-function
example's result and definitions, the bonus's retained loud call, the memory
measurement and this note. Add `--full` to show both full test runs as required.
The student must personally show it to the teacher by **6 November 2026, 23:59**
Europe/Kyiv.

Submission uses branch `practice-9`, a PR into `main`, and reviewer
`vovaskochko`. The supplied text has no numeric minimum of commits or coverage
percentage; work is separated into meaningful implementation, fixture,
verification, documentation and final-evidence commits. `ai_usage.txt` records
the literal user prompt, tools, accepted output and changes. Earlier disclosures
are preserved in docs. A Ukrainian walkthrough is in
[docs/practice9-explained.md](docs/practice9-explained.md).
