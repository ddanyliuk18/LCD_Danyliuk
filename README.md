# Languages and Compilers Design — Practice 3

Practice 3 implements a hand-written recursive-descent parser and an abstract syntax tree between the byte-level lexer and LLVM code generation.

The compiler pipeline is:

```text
source bytes -> lexer -> token vectors -> parser -> AST -> CodeGen visitor -> LLVM IR
```

The language supports `i32` declarations, optional `mut`, assignment to mutable variables, and a final `exit`. Initialisers and assignment values may contain chains of `+`, `-`, and `*`; multiplication has higher precedence, while operators at the same precedence are left-associative. `exit` still accepts only a constant or variable.

The grammar is documented in `grammar.ebnf`. The parser and AST are implemented without parser generators, regular expressions, or `eval`. LLVM IR is produced only through `llvmlite.ir` and serialized with `str(module)`.

## Compiler interface

Print lexer tokens (`text`, `kind`, `line:column`):

```bash
python3 compiler.py --tokens tests/valid1.txt
```

Print the AST without generating an output file:

```bash
python3 compiler.py --ast tests/valid1.txt
```

Compile to LLVM IR and run it:

```bash
python3 compiler.py tests/valid5.txt output.ll
lli output.ll
```

Expected output for `valid5.txt`:

```text
Program exit with result 120
```

## AST example

For `i32 x{2 + 3 * 4}`, the precedence is visible in the tree:

```text
Program
  Decl x const
    BinOp +
      Const 2
      BinOp *
        Const 3
        Const 4
  Exit
    Var x
```

## Tests

Run the complete suite in an environment with `llvmlite` and `lli`:

```bash
bash run_tests.sh
```

The valid cases check runtime output and exact `.ast` dumps. They cover the Practice 2 program, precedence, a multiplication in the middle of a chain, left associativity, and a full expression on the right of `:=`. Invalid cases cover parser, lexer, and AST-walk semantic errors with exact `line:column` positions.
