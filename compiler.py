import os
import sys

from llvmlite import ir
import llvmlite.binding as llvm


# ============================================================
# ERRORS
# ============================================================

class CompileError(Exception):
    pass


def error_at(line, col, message):
    raise CompileError(f"line {line}:{col}: {message}")


# ============================================================
# TOKENS
# ============================================================

class Token:
    def __init__(self, kind, text, line, col):
        self.kind = kind
        self.text = text
        self.line = line
        self.col = col

    def __repr__(self):
        return (
            f"Token("
            f"kind={self.kind!r}, "
            f"text={self.text!r}, "
            f"line={self.line}, "
            f"col={self.col}"
            f")"
        )


KEYWORDS = {
    "i32",
    "mut",
    "exit",
}


# ============================================================
# BYTE HELPERS
# ============================================================

def is_alpha(b):
    if b is None:
        return False

    return (
        ord("a") <= b <= ord("z")
        or ord("A") <= b <= ord("Z")
        or b == ord("_")
    )


def is_digit(b):
    if b is None:
        return False

    return ord("0") <= b <= ord("9")


# ============================================================
# TASK 1 — LEXER
# ============================================================

def lex(data: bytes):
    """
    Convert raw source bytes into token lists.

    One inner list = one source line.
    Lexer is a hand-written state machine.
    """

    lines = []
    tokens = []

    state = "START"

    # index where IDENT / NUMBER started
    start = 0

    # position of the first byte of current token
    start_line = 1
    start_col = 1

    line = 1
    col = 1
    i = 0

    # Remember an opening { so that it cannot cross a newline.
    open_brace_line = None
    open_brace_col = None

    while i <= len(data):
        b = data[i] if i < len(data) else None

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        if state == "START":

            # End of file
            if b is None:
                if open_brace_line is not None:
                    error_at(
                        open_brace_line,
                        open_brace_col,
                        "'{' is not closed before the end of the line",
                    )

                break

            # space or tab
            elif b in (32, 9):
                pass

            # newline
            elif b == 10:
                if open_brace_line is not None:
                    error_at(
                        open_brace_line,
                        open_brace_col,
                        "'{' is not closed before the end of the line",
                    )

                tokens.append(
                    Token(
                        "endline",
                        "\\n",
                        line,
                        col,
                    )
                )

                lines.append(tokens)
                tokens = []

                line += 1

                # At the bottom of the loop col += 1,
                # so set it to 0 here.
                col = 0

            # identifier / keyword begins
            elif is_alpha(b):
                state = "IDENT"

                start = i
                start_line = line
                start_col = col

            # number begins
            elif is_digit(b):
                state = "NUMBER"

                start = i
                start_line = line
                start_col = col

            # {
            elif b == ord("{"):
                tokens.append(
                    Token(
                        "block",
                        "{",
                        line,
                        col,
                    )
                )

                if open_brace_line is None:
                    open_brace_line = line
                    open_brace_col = col

            # }
            elif b == ord("}"):
                tokens.append(
                    Token(
                        "block",
                        "}",
                        line,
                        col,
                    )
                )

                open_brace_line = None
                open_brace_col = None

            # arithmetic operators
            elif b in (
                ord("+"),
                ord("-"),
                ord("*"),
            ):
                tokens.append(
                    Token(
                        "operator",
                        chr(b),
                        line,
                        col,
                    )
                )

            # := begins with :
            elif b == ord(":"):
                state = "COLON"

                start_line = line
                start_col = col

            # = alone is illegal
            elif b == ord("="):
                error_at(
                    line,
                    col,
                    "unexpected byte '='",
                )

            # ASCII only
            elif b > 127:
                error_at(
                    line,
                    col,
                    f"unexpected byte 0x{b:02x}",
                )

            # everything else is unknown
            else:
                try:
                    text = chr(b)
                except ValueError:
                    text = f"0x{b:02x}"

                error_at(
                    line,
                    col,
                    f"unexpected byte {text!r}",
                )

        # ----------------------------------------------------
        # IDENT
        # ----------------------------------------------------

        elif state == "IDENT":

            if (
                b is not None
                and (
                    is_alpha(b)
                    or is_digit(b)
                )
            ):
                # still part of the same word
                pass

            else:
                word_bytes = data[start:i]
                word = word_bytes.decode("ascii")

                if word in KEYWORDS:
                    kind = "keyword"
                else:
                    kind = "identifier"

                tokens.append(
                    Token(
                        kind,
                        word,
                        start_line,
                        start_col,
                    )
                )

                state = "START"

                # IMPORTANT:
                # current byte does not belong to IDENT.
                # Re-read it in START without advancing i/col.
                continue

        # ----------------------------------------------------
        # NUMBER
        # ----------------------------------------------------

        elif state == "NUMBER":

            if b is not None and is_digit(b):
                # still part of number
                pass

            elif b is not None and is_alpha(b):
                # e.g. 10x
                error_at(
                    line,
                    col,
                    "letter inside a number",
                )

            else:
                number_bytes = data[start:i]
                number = number_bytes.decode("ascii")

                tokens.append(
                    Token(
                        "number",
                        number,
                        start_line,
                        start_col,
                    )
                )

                state = "START"

                # Re-read delimiter in START.
                continue

        # ----------------------------------------------------
        # COLON — waiting for =
        # ----------------------------------------------------

        elif state == "COLON":

            if b == ord("="):
                tokens.append(
                    Token(
                        "operator",
                        ":=",
                        start_line,
                        start_col,
                    )
                )

                state = "START"

            else:
                error_at(
                    start_line,
                    start_col,
                    "':' is not followed by '='",
                )

        i += 1
        col += 1

    # Last source line may not end in \n
    if tokens:
        lines.append(tokens)

    return lines


def print_tokens(lines):
    for line_tokens in lines:
        for token in line_tokens:
            print(token)


# ============================================================
# LLVM SETUP
# ============================================================

I32 = ir.IntType(32)
I8 = ir.IntType(8)


def create_llvm():
    module = ir.Module(name="practice2")
    module.triple = llvm.get_default_triple()

    main = ir.Function(
        module,
        ir.FunctionType(I32, []),
        name="main",
    )

    builder = ir.IRBuilder(
        main.append_basic_block("entry")
    )

    printf = ir.Function(
        module,
        ir.FunctionType(
            I32,
            [ir.PointerType(I8)],
            var_arg=True,
        ),
        name="printf",
    )

    text = b"Program exit with result %d\n\0"

    fmt = ir.GlobalVariable(
        module,
        ir.ArrayType(I8, len(text)),
        name="fmt",
    )

    fmt.linkage = "private"
    fmt.global_constant = True

    fmt.initializer = ir.Constant(
        ir.ArrayType(I8, len(text)),
        bytearray(text),
    )

    return module, builder, printf, fmt


# ============================================================
# TASK 2 — TOKEN-BASED SYNTAX + CODE GENERATION
# ============================================================

class Symbol:
    def __init__(self, ptr, mutable):
        self.ptr = ptr
        self.mutable = mutable


def compile_tokens(token_lines):
    module, builder, printf, fmt = create_llvm()

    symbols = {}

    seen_exit = False

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def fail(token, message):
        error_at(
            token.line,
            token.col,
            message,
        )

    def value_from_token(token):
        if token.kind == "number":
            return ir.Constant(
                I32,
                int(token.text),
            )

        if token.kind == "identifier":
            if token.text not in symbols:
                fail(
                    token,
                    f"variable '{token.text}' "
                    "is used before its declaration",
                )

            return builder.load(
                symbols[token.text].ptr
            )

        fail(
            token,
            "expected a number or variable",
        )

    def compile_expression(expr_tokens):
        """
        Allowed expressions:

        10
        x
        x + 3
        2 * y
        """

        if len(expr_tokens) == 1:
            return value_from_token(
                expr_tokens[0]
            )

        if len(expr_tokens) == 3:
            lhs = expr_tokens[0]
            op = expr_tokens[1]
            rhs = expr_tokens[2]

            if (
                op.kind != "operator"
                or op.text not in ("+", "-", "*")
            ):
                fail(
                    op,
                    "expected arithmetic operator",
                )

            lhs_value = value_from_token(lhs)
            rhs_value = value_from_token(rhs)

            if op.text == "+":
                return builder.add(
                    lhs_value,
                    rhs_value,
                )

            if op.text == "-":
                return builder.sub(
                    lhs_value,
                    rhs_value,
                )

            return builder.mul(
                lhs_value,
                rhs_value,
            )

        if expr_tokens:
            fail(
                expr_tokens[0],
                "invalid expression",
            )

        raise CompileError(
            "line 1:1: empty expression"
        )

    # --------------------------------------------------------
    # Statements
    # --------------------------------------------------------

    for line_tokens in token_lines:

        # Remove endline token from syntax processing.
        tokens = [
            token
            for token in line_tokens
            if token.kind != "endline"
        ]

        # Blank line
        if not tokens:
            continue

        first = tokens[0]

        if seen_exit:
            fail(
                first,
                "statement after exit",
            )

        # ====================================================
        # DECLARATION
        #
        # i32 x{5}
        # i32 mut y{10}
        # ====================================================

        if (
            first.kind == "keyword"
            and first.text == "i32"
        ):
            index = 1
            mutable = False

            # optional mut
            if (
                index < len(tokens)
                and tokens[index].kind == "keyword"
                and tokens[index].text == "mut"
            ):
                mutable = True
                index += 1

            # variable name
            if index >= len(tokens):
                fail(
                    first,
                    "expected variable name",
                )

            name_token = tokens[index]

            if name_token.kind != "identifier":
                fail(
                    name_token,
                    "expected variable name",
                )

            name = name_token.text
            index += 1

            if name in symbols:
                fail(
                    name_token,
                    f"variable '{name}' is already declared",
                )

            # mandatory {
            if (
                index >= len(tokens)
                or tokens[index].kind != "block"
                or tokens[index].text != "{"
            ):
                if index < len(tokens):
                    bad = tokens[index]
                    fail(
                        bad,
                        f"variable '{name}' "
                        "needs an initialiser in {}",
                    )

                fail(
                    name_token,
                    f"variable '{name}' "
                    "needs an initialiser in {}",
                )

            index += 1

            expr_start = index

            # Find }
            while (
                index < len(tokens)
                and not (
                    tokens[index].kind == "block"
                    and tokens[index].text == "}"
                )
            ):
                index += 1

            if index >= len(tokens):
                fail(
                    name_token,
                    f"variable '{name}' "
                    "needs a closing '}'",
                )

            expr_tokens = tokens[
                expr_start:index
            ]

            if not expr_tokens:
                fail(
                    tokens[index],
                    "empty initialiser",
                )

            value = compile_expression(
                expr_tokens
            )

            index += 1

            # no extra tokens after }
            if index != len(tokens):
                fail(
                    tokens[index],
                    "extra tokens after declaration",
                )

            ptr = builder.alloca(
                I32,
                name=name,
            )

            builder.store(
                value,
                ptr,
            )

            symbols[name] = Symbol(
                ptr,
                mutable,
            )

        # ====================================================
        # EXIT
        #
        # exit y
        # exit 42
        # ====================================================

        elif (
            first.kind == "keyword"
            and first.text == "exit"
        ):
            if len(tokens) != 2:
                fail(
                    first,
                    "exit expects exactly one value",
                )

            value_token = tokens[1]

            value = value_from_token(
                value_token
            )

            builder.call(
                printf,
                [
                    builder.bitcast(
                        fmt,
                        ir.PointerType(I8),
                    ),
                    value,
                ],
            )

            builder.ret(
                ir.Constant(I32, 0)
            )

            seen_exit = True

        # ====================================================
        # ASSIGNMENT
        #
        # y := 5
        # y := x
        # y := x + 3
        # ====================================================

        elif first.kind == "identifier":
            name = first.text

            if name not in symbols:
                fail(
                    first,
                    f"variable '{name}' "
                    "is used before its declaration",
                )

            if (
                len(tokens) < 3
                or tokens[1].kind != "operator"
                or tokens[1].text != ":="
            ):
                fail(
                    first,
                    "invalid assignment",
                )

            symbol = symbols[name]

            if not symbol.mutable:
                fail(
                    first,
                    f"cannot assign to '{name}': "
                    "it is not mut",
                )

            expr_tokens = tokens[2:]

            value = compile_expression(
                expr_tokens
            )

            builder.store(
                value,
                symbol.ptr,
            )

        # ====================================================
        # ANYTHING ELSE
        # ====================================================

        else:
            fail(
                first,
                "invalid statement",
            )

    # Program must have exit.
    if not seen_exit:
        # We need a sensible position.
        for line_tokens in reversed(token_lines):
            real = [
                t
                for t in line_tokens
                if t.kind != "endline"
            ]

            if real:
                last = real[-1]

                error_at(
                    last.line,
                    last.col,
                    "program has no exit",
                )

        error_at(
            1,
            1,
            "program has no exit",
        )

    return module


# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) != 3:
        print(
            "usage: python3 compiler.py "
            "input.txt output.ll",
            file=sys.stderr,
        )
        return 1

    source_path = sys.argv[1]
    output_path = sys.argv[2]

    # On error no old output file should survive.
    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        # IMPORTANT:
        # Practice 2 lexer reads BYTES.
        with open(source_path, "rb") as f:
            data = f.read()

        token_lines = lex(data)

        module = compile_tokens(
            token_lines
        )

        # IR is written once, through str(module).
        with open(
            output_path,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(str(module))

        return 0

    except CompileError as e:
        print(
            f"compilation error: {e}",
            file=sys.stderr,
        )

        if os.path.exists(output_path):
            os.remove(output_path)

        return 1


if __name__ == "__main__":
    sys.exit(main())