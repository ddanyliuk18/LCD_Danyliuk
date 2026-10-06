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
    "i64",
    "bool",
    "mut",
    "exit",
    "true",
    "false",
    "if",
    "else",
    "while",
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

    # Accept files created by Windows editors while keeping the lexer byte-based.
    data = data.replace(b"\r\n", b"\n")

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

    while i <= len(data):
        b = data[i] if i < len(data) else None

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        if state == "START":

            # End of file
            if b is None:
                break

            # space or tab
            elif b in (32, 9):
                pass

            # newline
            elif b == 10:
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

            # comparisons begin with = or !
            elif b == ord("="):
                state = "EQUAL"
                start_line = line
                start_col = col

            elif b == ord("!"):
                state = "BANG"
                start_line = line
                start_col = col

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

        elif state == "EQUAL":
            if b == ord("="):
                tokens.append(Token("operator", "==", start_line, start_col))
                state = "START"
            else:
                error_at(start_line, start_col, "expected '==' (a single '=' is not an operator)")

        elif state == "BANG":
            if b == ord("="):
                tokens.append(Token("operator", "!=", start_line, start_col))
                state = "START"
            else:
                tokens.append(Token("operator", "!", start_line, start_col))
                state = "START"
                continue

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
    def __init__(self, line, col, name, type_name, mutable, init):
        super().__init__(line, col)
        self.name = name
        self.type_name = type_name
        self.mutable = mutable
        self.init = init

    def label(self):
        qualifier = "mut" if self.mutable else "const"
        return f"Decl {self.name} {self.type_name} {qualifier}"

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


class BlockNode(Node):
    def __init__(self, line, col, statements, exit_node=None):
        super().__init__(line, col)
        self.statements = statements
        self.exit = exit_node

    def label(self):
        return "Block"

    def children(self):
        return self.statements + ([self.exit] if self.exit is not None else [])


class IfNode(StmtNode):
    def __init__(self, line, col, condition, then_block, else_block=None):
        super().__init__(line, col)
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block

    def label(self):
        return "If"

    def children(self):
        children = [self.condition, self.then_block]
        if self.else_block is not None:
            children.append(self.else_block)
        return children


class WhileNode(StmtNode):
    def __init__(self, line, col, condition, body):
        super().__init__(line, col)
        self.condition = condition
        self.body = body

    def label(self):
        return "While"

    def children(self):
        return [self.condition, self.body]


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


class BoolNode(ExprNode):
    def __init__(self, line, col, value):
        super().__init__(line, col)
        self.value = value

    def label(self):
        return f"Bool {'true' if self.value else 'false'}"


class NotNode(ExprNode):
    def __init__(self, line, col, operand):
        super().__init__(line, col)
        self.operand = operand

    def label(self):
        return "Not"

    def children(self):
        return [self.operand]


# ============================================================
# RECURSIVE-DESCENT PARSER
# ============================================================

class Parser:
    def __init__(self, lines):
        self.lines = lines
        self.line_pos = 0
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

        if line_tokens:
            last = line_tokens[-1]
            self.line = last.line
            self.end_col = last.col + len(last.text)
        elif endline is not None:
            self.line = endline.line
            self.end_col = 1

    def next_line(self):
        if self.line_pos >= len(self.lines):
            return False
        self.set_line(self.lines[self.line_pos])
        self.line_pos += 1
        return True

    def finish_line(self):
        extra = self.peek()
        if extra is not None:
            self.fail(f"unexpected {extra.text!r} after the statement", extra)

    def parse_program(self):
        statements = []
        exit_node = None
        last_line = 1
        last_col = 1

        while self.next_line():
            last_line = self.line
            last_col = self.end_col

            if not self.toks:
                continue

            first = self.peek()
            if exit_node is not None:
                self.fail("statement after exit", first)

            if first.text == "else":
                self.fail("'else' without an 'if'", first)
            if first.text == "exit":
                exit_node = self.parse_exit()
                self.finish_line()
            else:
                statement = self.parse_statement()
                statements.append(statement)
                if not isinstance(statement, (IfNode, WhileNode)):
                    self.finish_line()

        if exit_node is None:
            error_at(last_line, last_col, "program has no exit")

        return ProgramNode(1, 1, statements, exit_node)

    def parse_statement(self):
        token = self.peek()
        if token.text in ("i32", "i64", "bool"):
            return self.parse_decl()
        if token.kind == "identifier":
            return self.parse_assign()
        if token.text == "if":
            return self.parse_if()
        if token.text == "while":
            return self.parse_while()
        self.fail(
            f"cannot start a statement with {token.text!r}",
            token,
        )

    def parse_if(self):
        keyword = self.expect_text("if")
        condition = self.parse_expr()
        self.finish_line()

        if not self.next_line():
            error_at(keyword.line, keyword.col, "expected '{' on its own line after 'if', found end of file")
        if not self.toks or self.toks[0].text != "{":
            token = self.toks[0] if self.toks else None
            if token is None:
                self.fail("expected '{' on its own line after 'if', found empty line")
            self.fail(f"expected '{{' on its own line after 'if', got {token.text!r}", token)
        then_block = self.parse_block()

        else_block = None
        if self.line_pos < len(self.lines):
            saved = self.line_pos
            self.next_line()
            if self.toks and self.toks[0].text == "else":
                else_token = self.eat()
                self.finish_line()
                if not self.next_line():
                    error_at(else_token.line, else_token.col, "expected '{' on its own line after 'else', found end of file")
                if not self.toks or self.toks[0].text != "{":
                    token = self.toks[0] if self.toks else None
                    if token is None:
                        self.fail("expected '{' on its own line after 'else', found empty line")
                    self.fail(f"expected '{{' on its own line after 'else', got {token.text!r}", token)
                else_block = self.parse_block()
            else:
                self.line_pos = saved

        return IfNode(keyword.line, keyword.col, condition, then_block, else_block)

    def parse_while(self):
        keyword = self.expect_text("while")
        condition = self.parse_expr()
        self.finish_line()

        if not self.next_line():
            error_at(keyword.line, keyword.col, "expected '{' on its own line after 'while', found end of file")
        if not self.toks or self.toks[0].text != "{":
            token = self.toks[0] if self.toks else None
            if token is None:
                self.fail("expected '{' on its own line after 'while', found empty line")
            self.fail(f"expected '{{' on its own line after 'while', got {token.text!r}", token)
        body = self.parse_block()
        return WhileNode(keyword.line, keyword.col, condition, body)

    def parse_block(self):
        opening = self.expect_text("{")
        self.finish_line()
        statements = []
        exit_node = None

        while self.next_line():
            if not self.toks:
                continue
            first = self.peek()
            if first.text == "}":
                self.eat()
                self.finish_line()
                if not statements and exit_node is None:
                    error_at(opening.line, opening.col, "empty block")
                return BlockNode(opening.line, opening.col, statements, exit_node)
            if first.text == "else":
                self.fail("'else' without an 'if'", first)
            if exit_node is not None:
                self.fail("statement after 'exit' in the same block", first)
            if first.text == "exit":
                exit_node = self.parse_exit()
                self.finish_line()
            else:
                statement = self.parse_statement()
                statements.append(statement)
                if not isinstance(statement, (IfNode, WhileNode)):
                    self.finish_line()

        error_at(opening.line, opening.col, "'{' is never closed")

    def parse_decl(self):
        type_token = self.eat()
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
            type_token.text,
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
        node = self.parse_arith()

        if self.peek() is not None and self.peek().text in ("==", "!="):
            operator = self.eat()
            right = self.parse_arith()
            node = BinOpNode(operator.line, operator.col, operator.text, node, right)

        return node

    def parse_arith(self):
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

        if token.text == "!":
            self.eat()
            return NotNode(token.line, token.col, self.parse_factor())

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

        if token.text in ("true", "false"):
            self.eat()
            return BoolNode(token.line, token.col, token.text == "true")

        self.fail(
            f"expected a constant or a variable, got {token.text!r}",
            token,
        )


# ============================================================
# SEMANTIC CHECKER
# ============================================================

INTEGER_TYPES = ("i32", "i64")


class SemanticChecker:
    def __init__(self):
        self.scopes = [{}]

    def visit(self, node):
        method_name = "visit_" + node.__class__.__name__.removesuffix("Node").lower()
        return getattr(self, method_name)(node)

    def fail(self, node, message):
        error_at(node.line, node.col, message)

    def visit_program(self, node):
        for statement in node.statements:
            self.visit(statement)
        self.visit(node.exit)

    def visit_decl(self, node):
        frame = self.scopes[-1]
        if node.name in frame:
            self.fail(node, f"variable '{node.name}' is already declared in this block")
        self.visit(node.init)
        self.check_assignable(
            node.init, node.type_name, node,
            f"initialise '{node.name}'",
        )
        frame[node.name] = node

    def visit_block(self, node):
        self.scopes.append({})
        for statement in node.statements:
            self.visit(statement)
        if node.exit is not None:
            self.visit(node.exit)
        self.scopes.pop()

    def visit_if(self, node):
        condition_type = self.visit(node.condition)
        if condition_type != "bool":
            self.fail(node, f"the condition of 'if' must be bool, got {condition_type}")
        self.visit(node.then_block)
        if node.else_block is not None:
            self.visit(node.else_block)

    def visit_while(self, node):
        condition_type = self.visit(node.condition)
        if condition_type != "bool":
            self.fail(node, f"the condition of 'while' must be bool, got {condition_type}")
        self.visit(node.body)

    def visit_assign(self, node):
        decl = self.resolve(node, node.name)
        node.decl = decl
        if not decl.mutable:
            self.fail(node, f"cannot assign to '{node.name}': it is not mut")
        self.visit(node.value)
        self.check_assignable(
            node.value, decl.type_name, node,
            f"assign to '{node.name}'",
        )

    def visit_exit(self, node):
        self.visit(node.value)

    def visit_binop(self, node):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        if node.op in ("+", "-", "*"):
            if left_type not in INTEGER_TYPES:
                self.fail(node, f"cannot apply '{node.op}' to {left_type}")
            if right_type not in INTEGER_TYPES:
                self.fail(node, f"cannot apply '{node.op}' to {right_type}")
            node.type = "i64" if "i64" in (left_type, right_type) else "i32"
        else:
            both_int = left_type in INTEGER_TYPES and right_type in INTEGER_TYPES
            both_bool = left_type == right_type == "bool"
            if not (both_int or both_bool):
                self.fail(node, f"cannot compare {left_type} with {right_type}")
            node.type = "bool"
        return node.type

    def visit_var(self, node):
        node.decl = self.resolve(node, node.name)
        node.type = node.decl.type_name
        return node.type

    def visit_const(self, node):
        if node.value <= 2**31 - 1:
            node.type = "i32"
        elif node.value <= 2**63 - 1:
            node.type = "i64"
        else:
            self.fail(node, f"constant {node.value} does not fit in i64")
        return node.type

    def visit_bool(self, node):
        node.type = "bool"
        return node.type

    def visit_not(self, node):
        operand_type = self.visit(node.operand)
        if operand_type != "bool":
            self.fail(node, f"cannot apply '!' to {operand_type}")
        node.type = "bool"
        return node.type

    def resolve(self, node, name):
        for frame in reversed(self.scopes):
            if name in frame:
                return frame[name]
        self.fail(node, f"variable '{name}' is used before its declaration")

    def check_assignable(self, expr, want, at, what):
        have = expr.type
        if have == want or (have == "i32" and want == "i64"):
            return
        if isinstance(expr, ConstNode) and want == "i32" and have == "i64":
            self.fail(expr, f"constant {expr.value} does not fit in i32")
        self.fail(
            at,
            f"cannot {what} of type {want} with a value of type {have}",
        )


# ============================================================
# LLVM SETUP
# ============================================================

I1 = ir.IntType(1)
I32 = ir.IntType(32)
I64 = ir.IntType(64)
I8 = ir.IntType(8)
LLVM_TYPES = {"bool": I1, "i32": I32, "i64": I64}


def create_llvm():
    module = ir.Module(name="practice5")
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

    def global_text(name, text):
        data = text + b"\0"
        value = ir.GlobalVariable(module, ir.ArrayType(I8, len(data)), name=name)
        value.linkage = "private"
        value.global_constant = True
        value.initializer = ir.Constant(ir.ArrayType(I8, len(data)), bytearray(data))
        return value

    int_fmt = global_text("int_fmt", b"Program exit with result %lld\n")
    bool_fmt = global_text("bool_fmt", b"Program exit with result %s\n")
    true_text = global_text("true_text", b"true")
    false_text = global_text("false_text", b"false")
    return module, builder, printf, int_fmt, bool_fmt, true_text, false_text


# ============================================================
# CODE GENERATION VISITOR
# ============================================================

class CodeGen:
    def __init__(self):
        (
            self.module,
            self.builder,
            self.printf,
            self.int_fmt,
            self.bool_fmt,
            self.true_text,
            self.false_text,
        ) = create_llvm()

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
        value = self.visit(node.init)
        value = self.coerce(value, node.init.type, node.type_name)
        node.ptr = self.alloca_in_entry(LLVM_TYPES[node.type_name], node.name)
        self.builder.store(value, node.ptr)

    def alloca_in_entry(self, llvm_type, name):
        current_block = self.builder.block
        entry = self.builder.function.entry_basic_block
        if entry.instructions:
            self.builder.position_before(entry.instructions[0])
        else:
            self.builder.position_at_end(entry)
        slot = self.builder.alloca(llvm_type, name=name)
        self.builder.position_at_end(current_block)
        return slot

    def visit_block(self, node):
        for statement in node.statements:
            self.visit(statement)
        if node.exit is not None:
            self.visit(node.exit)

    def visit_if(self, node):
        condition = self.visit(node.condition)
        function = self.builder.function
        then_bb = function.append_basic_block("then")
        else_bb = function.append_basic_block("else") if node.else_block else None
        merge_bb = function.append_basic_block("merge")
        self.builder.cbranch(condition, then_bb, else_bb or merge_bb)

        self.builder.position_at_end(then_bb)
        self.visit(node.then_block)
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_bb)

        if else_bb is not None:
            self.builder.position_at_end(else_bb)
            self.visit(node.else_block)
            if not self.builder.block.is_terminated:
                self.builder.branch(merge_bb)

        self.builder.position_at_end(merge_bb)

    def visit_while(self, node):
        function = self.builder.function
        condition_bb = function.append_basic_block("while.cond")
        body_bb = function.append_basic_block("while.body")
        end_bb = function.append_basic_block("while.end")

        self.builder.branch(condition_bb)
        self.builder.position_at_end(condition_bb)
        condition = self.visit(node.condition)
        self.builder.cbranch(condition, body_bb, end_bb)

        self.builder.position_at_end(body_bb)
        self.visit(node.body)
        if not self.builder.block.is_terminated:
            self.builder.branch(condition_bb)

        self.builder.position_at_end(end_bb)

    def visit_assign(self, node):
        value = self.visit(node.value)
        value = self.coerce(value, node.value.type, node.decl.type_name)
        self.builder.store(value, node.decl.ptr)

    def visit_exit(self, node):
        value = self.visit(node.value)
        if node.value.type == "bool":
            selected = self.builder.select(
                value,
                self.builder.bitcast(self.true_text, ir.PointerType(I8)),
                self.builder.bitcast(self.false_text, ir.PointerType(I8)),
                name="bool_text",
            )
            fmt = self.bool_fmt
            argument = selected
        else:
            fmt = self.int_fmt
            argument = self.coerce(value, node.value.type, "i64")
        self.builder.call(
            self.printf,
            [
                self.builder.bitcast(fmt, ir.PointerType(I8)),
                argument,
            ],
        )
        self.builder.ret(ir.Constant(I32, 0))

    def visit_binop(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)

        operand_type = node.type
        if node.op in ("==", "!="):
            operand_type = "i64" if "i64" in (node.left.type, node.right.type) else node.left.type
        left = self.coerce(left, node.left.type, operand_type)
        right = self.coerce(right, node.right.type, operand_type)

        if node.op == "+":
            return self.builder.add(left, right)
        if node.op == "-":
            return self.builder.sub(left, right)
        if node.op == "*":
            return self.builder.mul(left, right)
        predicate = "==" if node.op == "==" else "!="
        return self.builder.icmp_signed(predicate, left, right)

    def visit_var(self, node):
        return self.builder.load(node.decl.ptr)

    def visit_const(self, node):
        return ir.Constant(LLVM_TYPES[node.type], node.value)

    def visit_bool(self, node):
        return ir.Constant(I1, node.value)

    def visit_not(self, node):
        return self.builder.xor(self.visit(node.operand), ir.Constant(I1, 1), name="not")

    def coerce(self, value, have, want):
        if have == "i32" and want == "i64":
            return self.builder.sext(value, I64, name="wide")
        return value


def compile_tree(tree):
    SemanticChecker().visit(tree)
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

        SemanticChecker().visit(tree)

        if sys.argv[1] == "--ast":
            tree.dump()
            return 0

        module = CodeGen().visit(tree)

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
