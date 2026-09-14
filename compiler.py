import sys
import os
import re

from llvmlite import ir
import llvmlite.binding as llvm


I32 = ir.IntType(32)
I8 = ir.IntType(8)

module = ir.Module(name="practice1")
module.triple = llvm.get_default_triple()

main = ir.Function(
    module,
    ir.FunctionType(I32, []),
    name="main"
)

builder = ir.IRBuilder(
    main.append_basic_block("entry")
)

printf = ir.Function(
    module,
    ir.FunctionType(
        I32,
        [ir.PointerType(I8)],
        var_arg=True
    ),
    name="printf"
)

text = b"Program exit with result %d\n\0"

fmt = ir.GlobalVariable(
    module,
    ir.ArrayType(I8, len(text)),
    name="fmt"
)

fmt.linkage = "private"
fmt.global_constant = True
fmt.initializer = ir.Constant(
    ir.ArrayType(I8, len(text)),
    bytearray(text)
)

symbols = {}


def compilation_error(line_number, message):
    print(
        f"compilation error: line {line_number}: {message}",
        file=sys.stderr
    )
    sys.exit(1)


def get_value(token, line_number):
    token = token.strip()

    if token.isdigit():
        return ir.Constant(I32, int(token))

    if token not in symbols:
        compilation_error(
            line_number,
            f"undeclared variable '{token}'"
        )

    return builder.load(symbols[token])


if len(sys.argv) != 3:
    print(
        "usage: python3 compiler.py input.txt output.ll",
        file=sys.stderr
    )
    sys.exit(1)

source_path = sys.argv[1]
out_path = sys.argv[2]

if os.path.exists(out_path):
    os.remove(out_path)

with open(source_path) as f:
    lines = f.readlines()

seen_exit = False
last_line_number = 1


for line_number, raw_line in enumerate(lines, start=1):
    last_line_number = line_number
    line = raw_line.strip()

    if not line:
        continue

    if seen_exit:
        compilation_error(
            line_number,
            "statement after exit"
        )

    if line.startswith("int "):
        parts = line.split()

        if len(parts) != 2:
            compilation_error(
                line_number,
                "invalid declaration"
            )

        name = parts[1]

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            compilation_error(
                line_number,
                f"invalid variable name '{name}'"
            )

        if name in ("int", "exit"):
            compilation_error(
                line_number,
                f"reserved name '{name}'"
            )

        if name in symbols:
            compilation_error(
                line_number,
                f"variable '{name}' already declared"
            )

        symbols[name] = builder.alloca(
            I32,
            name=name
        )

    elif ":=" in line:
        parts = line.split(":=")

        if len(parts) != 2:
            compilation_error(
                line_number,
                "invalid assignment"
            )

        name = parts[0].strip()
        expr = parts[1].strip()

        if name not in symbols:
            compilation_error(
                line_number,
                f"undeclared variable '{name}'"
            )

        match = re.fullmatch(
            r"([A-Za-z_][A-Za-z0-9_]*|\d+)"
            r"\s*([+\-*])\s*"
            r"([A-Za-z_][A-Za-z0-9_]*|\d+)",
            expr
        )

        if match:
            lhs, operator, rhs = match.groups()

            lhs_value = get_value(lhs, line_number)
            rhs_value = get_value(rhs, line_number)

            if operator == "+":
                result = builder.add(lhs_value, rhs_value)

            elif operator == "-":
                result = builder.sub(lhs_value, rhs_value)

            else:
                result = builder.mul(lhs_value, rhs_value)

        else:
            simple = re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*|\d+",
                expr
            )

            if not simple:
                compilation_error(
                    line_number,
                    "invalid expression"
                )

            result = get_value(expr, line_number)

        builder.store(
            result,
            symbols[name]
        )

    elif line.startswith("exit "):
        parts = line.split()

        if len(parts) != 2:
            compilation_error(
                line_number,
                "invalid exit statement"
            )

        name = parts[1]

        if name not in symbols:
            compilation_error(
                line_number,
                f"undeclared variable '{name}'"
            )

        value = builder.load(symbols[name])

        builder.call(
            printf,
            [
                builder.bitcast(
                    fmt,
                    ir.PointerType(I8)
                ),
                value
            ]
        )

        builder.ret(
            ir.Constant(I32, 0)
        )

        seen_exit = True

    else:
        compilation_error(
            line_number,
            "cannot parse statement"
        )


if not seen_exit:
    compilation_error(
        last_line_number,
        "missing exit statement"
    )


with open(out_path, "w") as f:
    f.write(str(module))
