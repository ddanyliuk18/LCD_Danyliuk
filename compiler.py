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


def main():
    if len(sys.argv) != 2:
        print(
            "usage: python3 compiler.py input.txt",
            file=sys.stderr,
        )
        return 1

    try:
        with open(sys.argv[1], "rb") as f:
            data = f.read()

        token_lines = lex(data)
        print_tokens(token_lines)
        return 0

    except CompileError as e:
        print(
            f"compilation error: {e}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())