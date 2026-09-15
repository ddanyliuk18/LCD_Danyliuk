# Languages and Compilers Design — Practice 2

Practice 2 implements a hand-written byte-by-byte lexer and a token-based compiler frontend in Python using `llvmlite`.

The compiler supports:

- `i32` declarations;
- immutable variables by default;
- `mut` variables;
- mandatory initializers;
- integer constants and variables;
- arithmetic operators `+`, `-`, `*`;
- assignment with `:=`;
- `exit`;
- lexical and semantic errors with `line:column` positions.

## Example

```text
i32 x{0}
i32 mut y{10}
i32 z{2+5}
i32 mut t { x + 10 }
t := t * z
exit t
Expected output:

Program exit with result 70
Run the compiler

Activate the environment with llvmlite installed:

source ~/lcd/bin/activate

Compile source code to LLVM IR:

python3 compiler.py input.txt output.ll

Run the generated LLVM IR:

lli output.ll

Or compile it to an object file and executable:

llc -filetype=obj -relocation-model=pic output.ll -o output.o
clang -fPIE output.o -o program
./program
Run tests

The test suite contains 5 valid and 5 invalid programs.

bash run_tests.sh

Expected result:

=== RESULT ===
Passed: 10
Failed: 0

Invalid tests verify that incorrect programs are rejected with:

a non-zero exit code;
the expected error message;
the correct line:column;
no generated output.ll.
