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

## Worked example

```text
i32 x{5}
i32 mut y{10}
y := x + 3
exit y
```

Print the lexer output (columns are `text`, `kind`, and `line:column`):

```bash
python3 compiler.py --tokens tests/valid1.txt
```

```text
'i32'   keyword     1:1
'x'     identifier  1:5
'{'     block       1:6
'5'     number      1:7
'}'     block       1:8
'\\n'   endline     1:9
'i32'   keyword     2:1
'mut'   keyword     2:5
'y'     identifier  2:9
'{'     block       2:10
'10'    number      2:11
'}'     block       2:13
'\\n'   endline     2:14
'y'     identifier  3:1
':='    operator    3:3
'x'     identifier  3:6
'+'     operator    3:8
'3'     number      3:10
'\\n'   endline     3:11
'exit'  keyword     4:1
'y'     identifier  4:6
'\\n'   endline     4:7
```

Compile the program to LLVM IR:

```bash
python3 compiler.py tests/valid1.txt output.ll
```

Run the generated LLVM IR:

```bash
lli output.ll
```

Expected output:

```text
Program exit with result 8
```

Alternatively, compile it to an object file and executable:

```bash
llc -filetype=obj -relocation-model=pic output.ll -o output.o
clang -fPIE output.o -o program
./program
```

## Run tests

Activate an environment with `llvmlite` installed, then run:

```bash
bash run_tests.sh
```

The suite contains five valid and five invalid programs. Expected result:

```text
=== RESULT ===
Passed: 10
Failed: 0
```

Invalid tests verify that incorrect programs are rejected with a non-zero exit code, the expected error and `line:column`, and no generated `output.ll`.
