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
            print(
                f"{token.text!r}\t"
                f"{token.kind}\t"
                f"{token.line}:{token.col}"
            )


# ============================================================
# ABSTRACT SYNTAX TREE
# ============================================================

class Node:
    def __init__(self, line, col):
        self.line = line
        self.col = col

    def dump(self, indent=0):
        print("  " * indent + self.label())
        for child in self.children():
            child.dump(indent + 1)

    def children(self):
        return []


class ProgramNode(Node):
    def __init__(self, line, col, statements, exit_node):
        super().__init__(line, col)
        self.statements = statements
        self.exit = exit_node

    def label(self):
        return "Program"

    def children(self):
        return self.statements + [self.exit]


class StmtNode(Node):
    pass


class DeclNode(StmtNode):
    def __init__(self, line, col, name, mutable, init):
        super().__init__(line, col)
        self.name = name
        self.mutable = mutable
        self.init = init

    def label(self):
        qualifier = "mut" if self.mutable else "const"
        return f"Decl {self.name} {qualifier}"

    def children(self):
        return [self.init]


class AssignNode(StmtNode):
    def __init__(self, line, col, name, value):
        super().__init__(line, col)
        self.name = name
        self.value = value

    def label(self):
        return f"Assign {self.name}"

    def children(self):
        return [self.value]


class ExitNode(Node):
    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value

    def label(self):
        return "Exit"

    def children(self):
        return [self.value]


class ExprNode(Node):
    pass


class BinOpNode(ExprNode):
    def __init__(self, line, col, op, left, right):
        super().__init__(line, col)
        self.op = op
        self.left = left
        self.right = right

    def label(self):
        return f"BinOp {self.op}"

    def children(self):
        return [self.left, self.right]


class VarNode(ExprNode):
    def __init__(self, line, col, name):
        super().__init__(line, col)
        self.name = name

    def label(self):
        return f"Var {self.name}"


class ConstNode(ExprNode):
    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value

    def label(self):
        return f"Const {self.value}"


# ============================================================
# RECURSIVE-DESCENT PARSER
# ============================================================

class Parser:
    def __init__(self, lines):
        self.lines = lines
        self.toks = []
        self.pos = 0
        self.line = 1
        self.end_col = 1

    def peek(self):
        if self.pos < len(self.toks):
            return self.toks[self.pos]
        return None

    def eat(self):
        token = self.toks[self.pos]
        self.pos += 1
        return token

    def fail(self, message, token=None):
        if token is None:
            token = self.peek()

        if token is None:
            error_at(self.line, self.end_col, message)

        error_at(token.line, token.col, message)

    def expect_text(self, text, what=None):
        token = self.peek()
        if token is None or token.text != text:
            expected = what if what is not None else repr(text)
            if token is None:
                self.fail(f"expected {expected}, found end of line")
            self.fail(f"expected {expected}, got {token.text!r}", token)
        return self.eat()

    def expect_kind(self, kind, what):
        token = self.peek()
        if token is None or token.kind != kind:
            if token is None:
                self.fail(f"expected {what}, found end of line")
            self.fail(f"expected {what}, got {token.text!r}", token)
        return self.eat()

    def set_line(self, line_tokens):
        endline = None
        if line_tokens and line_tokens[-1].kind == "endline":
            endline = line_tokens[-1]
            line_tokens = line_tokens[:-1]

        self.toks = line_tokens
        self.pos = 0

        if endline is not None:
            self.line = endline.line
            self.end_col = endline.col
        elif line_tokens:
            last = line_tokens[-1]
            self.line = last.line
            self.end_col = last.col + len(last.text)

    def parse_program(self):
        statements = []
        exit_node = None
        last_line = 1
        last_col = 1

        for line_tokens in self.lines:
            self.set_line(line_tokens)
            last_line = self.line
            last_col = self.end_col

            if not self.toks:
                continue

            first = self.peek()
            if exit_node is not None:
                self.fail("statement after exit", first)

            if first.text == "exit":
                exit_node = self.parse_exit()
            else:
                statements.append(self.parse_statement())

            extra = self.peek()
            if extra is not None:
                self.fail(
                    f"unexpected {extra.text!r} after the statement",
                    extra,
                )

        if exit_node is None:
            error_at(last_line, last_col, "program has no exit")

        return ProgramNode(1, 1, statements, exit_node)

    def parse_statement(self):
        token = self.peek()
        if token.text == "i32":
            return self.parse_decl()
        if token.kind == "identifier":
            return self.parse_assign()
        self.fail(
            f"cannot start a statement with {token.text!r}",
            token,
        )

    def parse_decl(self):
        self.expect_text("i32")
        mutable = False

        if self.peek() is not None and self.peek().text == "mut":
            self.eat()
            mutable = True

        name = self.expect_kind("identifier", "a variable name")

        token = self.peek()
        if token is None or token.text != "{":
            self.fail(
                f"variable '{name.text}' needs an initialiser in {{}}",
                token if token is not None else name,
            )
        self.eat()

        init = self.parse_expr()
        self.expect_text("}", "'}'")

        return DeclNode(
            name.line,
            name.col,
            name.text,
            mutable,
            init,
        )

    def parse_assign(self):
        name = self.expect_kind("identifier", "a variable name")
        token = self.peek()
        if token is None or token.text != ":=":
            if token is None:
                self.fail(
                    f"expected ':=' after '{name.text}', found end of line"
                )
            self.fail(
                f"expected ':=' after '{name.text}', got {token.text!r}",
                token,
            )
        self.eat()
        value = self.parse_expr()
        return AssignNode(name.line, name.col, name.text, value)

    def parse_exit(self):
        keyword = self.expect_text("exit")
        value = self.parse_factor()
        return ExitNode(keyword.line, keyword.col, value)

    def parse_expr(self):
        node = self.parse_term()

        while (
            self.peek() is not None
            and self.peek().kind == "operator"
            and self.peek().text in ("+", "-")
        ):
            operator = self.eat()
            right = self.parse_term()
            node = BinOpNode(
                operator.line,
                operator.col,
                operator.text,
                node,
                right,
            )

        return node

    def parse_term(self):
        node = self.parse_factor()

        while (
            self.peek() is not None
            and self.peek().kind == "operator"
            and self.peek().text == "*"
        ):
            operator = self.eat()
            right = self.parse_factor()
            node = BinOpNode(
                operator.line,
                operator.col,
                operator.text,
                node,
                right,
            )

        return node

    def parse_factor(self):
        token = self.peek()
        if token is None:
            self.fail(
                "expected a constant or a variable, found end of line"
            )

        if token.kind == "number":
            self.eat()
            return ConstNode(
                token.line,
                token.col,
                int(token.text),
            )

        if token.kind == "identifier":
            self.eat()
            return VarNode(
                token.line,
                token.col,
                token.text,
            )

        self.fail(
            f"expected a constant or a variable, got {token.text!r}",
            token,
        )


# ============================================================
# LLVM SETUP
# ============================================================

I32 = ir.IntType(32)
I8 = ir.IntType(8)


def create_llvm():
    module = ir.Module(name="practice3")
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
# CODE GENERATION VISITOR
# ============================================================

class Symbol:
    def __init__(self, ptr, mutable):
        self.ptr = ptr
        self.mutable = mutable


class CodeGen:
    def __init__(self):
        (
            self.module,
            self.builder,
            self.printf,
            self.fmt,
        ) = create_llvm()
        self.symbols = {}

    def fail(self, node, message):
        error_at(node.line, node.col, message)

    def visit(self, node):
        method_name = "visit_" + node.__class__.__name__.removesuffix(
            "Node"
        ).lower()
        return getattr(self, method_name)(node)

    def visit_program(self, node):
        for statement in node.statements:
            self.visit(statement)
        self.visit(node.exit)
        return self.module

    def visit_decl(self, node):
        if node.name in self.symbols:
            self.fail(
                node,
                f"variable '{node.name}' is already declared",
            )

        value = self.visit(node.init)
        ptr = self.builder.alloca(I32, name=node.name)
        self.builder.store(value, ptr)
        self.symbols[node.name] = Symbol(ptr, node.mutable)

    def visit_assign(self, node):
        if node.name not in self.symbols:
            self.fail(
                node,
                f"variable '{node.name}' is used before its declaration",
            )

        symbol = self.symbols[node.name]
        if not symbol.mutable:
            self.fail(
                node,
                f"cannot assign to '{node.name}': it is not mut",
            )

        value = self.visit(node.value)
        self.builder.store(value, symbol.ptr)

    def visit_exit(self, node):
        value = self.visit(node.value)
        self.builder.call(
            self.printf,
            [
                self.builder.bitcast(
                    self.fmt,
                    ir.PointerType(I8),
                ),
                value,
            ],
        )
        self.builder.ret(ir.Constant(I32, 0))

    def visit_binop(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)

        if node.op == "+":
            return self.builder.add(left, right)
        if node.op == "-":
            return self.builder.sub(left, right)
        return self.builder.mul(left, right)

    def visit_var(self, node):
        if node.name not in self.symbols:
            self.fail(
                node,
                f"variable '{node.name}' is used before its declaration",
            )
        return self.builder.load(self.symbols[node.name].ptr)

    def visit_const(self, node):
        return ir.Constant(I32, node.value)


def compile_tree(tree):
    return CodeGen().visit(tree)


# ============================================================
# MAIN
# ============================================================

def main():
    dump_mode = (
        len(sys.argv) == 3
        and sys.argv[1] in ("--tokens", "--ast")
    )

    if (
        len(sys.argv) != 3
        or (
            sys.argv[1].startswith("--")
            and not dump_mode
        )
    ):
        print(
            "usage:\n"
            "  python3 compiler.py input.txt output.ll\n"
            "  python3 compiler.py --tokens input.txt\n"
            "  python3 compiler.py --ast input.txt",
            file=sys.stderr,
        )
        return 1

    if dump_mode:
        source_path = sys.argv[2]
        output_path = None
    else:
        source_path = sys.argv[1]
        output_path = sys.argv[2]

    # On error no old output file should survive.
    if output_path is not None and os.path.exists(output_path):
        os.remove(output_path)

    try:
        # IMPORTANT:
        # Practice 2 lexer reads BYTES.
        with open(source_path, "rb") as f:
            data = f.read()

        token_lines = lex(data)

        if sys.argv[1] == "--tokens":
            print_tokens(token_lines)
            return 0

        tree = Parser(token_lines).parse_program()

        if sys.argv[1] == "--ast":
            tree.dump()
            return 0

        module = compile_tree(tree)

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

        if output_path is not None and os.path.exists(output_path):
            os.remove(output_path)

        return 1


if __name__ == "__main__":
    sys.exit(main())
