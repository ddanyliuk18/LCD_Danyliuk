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
    "struct",
    "fn",
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

            elif b == ord('"'):
                closing = i + 1
                while closing < len(data) and data[closing] not in (10, 13, 34):
                    closing += 1
                if closing == len(data) or data[closing] != 34:
                    error_at(line, col, 'string literal is not closed on its line')
                tokens.append(Token('string', data[i + 1:closing].decode('latin1'), line, col))
                col += closing - i
                i = closing

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


            elif b in (ord('.'), ord(','), ord('('), ord(')')):
                tokens.append(Token("punctuation", chr(b), line, col))

            elif b == ord('-') and i + 1 < len(data) and data[i + 1] == ord('>'):
                tokens.append(Token("operator", "->", line, col))
                i += 1
                col += 1

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
        target = getattr(self, 'target', None)
        parts = []
        while isinstance(target, FieldNode):
            parts.append(target.name)
            target = target.base
        suffix = ''.join('.' + part for part in reversed(parts))
        return f"Assign {self.name}{suffix}"

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

class CoreParser:
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

    def next_nonempty_line(self):
        while self.next_line():
            if self.toks:
                return True
        return False

    def finish_line(self):
        extra = self.peek()
        if extra is not None:
            self.fail(f"unexpected {extra.text!r} after the statement", extra)


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

        if not self.next_nonempty_line():
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
            self.next_nonempty_line()
            if self.toks and self.toks[0].text == "else":
                else_token = self.eat()
                self.finish_line()
                if not self.next_nonempty_line():
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

        if not self.next_nonempty_line():
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


class CoreSemanticChecker:
    def __init__(self):
        self.scopes = [{}]

    def visit(self, node):
        method_name = "visit_" + node.__class__.__name__.removesuffix("Node").lower()
        return getattr(self, method_name)(node)

    def fail(self, node, message):
        error_at(node.line, node.col, message)


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
    module = ir.Module(name="practice6", context=ir.Context())
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

class CoreCodeGen:
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


class StructNode(Node):
    def __init__(self, token, fields):
        super().__init__(token.line, token.col)
        self.name, self.fields = token.text, fields
        self.methods = []

    def label(self):
        return f"Struct {self.name}"

    def children(self):
        return self.fields + self.methods


class FieldDeclNode(DeclNode):
    def label(self):
        return f"Field {self.name} {self.type_name} {'mut' if self.mutable else 'const'}"

    def children(self):
        return []


class FunctionNode(Node):
    def __init__(self, token, params, result, body):
        super().__init__(token.line, token.col)
        self.name, self.params, self.result, self.body = token.text, params, result, body

    def label(self):
        return f"Function {self.name} -> {self.result}"

    def children(self):
        return self.params + [self.body]


class CallNode(ExprNode):
    def __init__(self, token, args):
        super().__init__(token.line, token.col)
        self.name, self.args = token.text, args

    def label(self):
        return f"Call {self.name}"

    def children(self):
        return self.args


class MemberFnNode(FunctionNode):
    def label(self):
        return f'MemberFn {self.name} -> {self.result}'


class MemberCallNode(CallNode):
    def __init__(self, base, token, args):
        super().__init__(token, args)
        self.base = base

    def label(self):
        return f'MemberCall {self.name}'

    def children(self):
        return [self.base] + self.args


class StringNode(ExprNode):
    def __init__(self, token):
        super().__init__(token.line, token.col)
        self.value = token.text

    def label(self):
        return f'String {self.value!r}'


class PrintNode(StmtNode):
    def __init__(self, token, value):
        super().__init__(token.line, token.col)
        self.value = value

    def label(self):
        return 'Print'

    def children(self):
        return [self.value]


class FieldNode(ExprNode):
    def __init__(self, base, token):
        super().__init__(token.line, token.col)
        self.base, self.name = base, token.text

    def label(self):
        return f"FieldAccess {self.name}"

    def children(self):
        return [self.base]


class InitNode(ExprNode):
    def __init__(self, token, values):
        super().__init__(token.line, token.col)
        self.values = values

    def label(self):
        return f"Init {self.type}"

    def children(self):
        return self.values


class Parser(CoreParser):
    def parse_type(self):
        token = self.peek()
        if token is None or not (token.text in LLVM_TYPES or token.kind == 'identifier'):
            self.fail('expected a type', token)
        return self.eat()

    def block_after(self, keyword):
        if not self.next_nonempty_line():
            self.fail(f"expected '{{' after '{keyword}'")
        return self.parse_block()

    def parse_struct(self):
        self.eat()
        name = self.expect_kind('identifier', 'a struct name')
        self.finish_line()
        if not self.next_nonempty_line():
            self.fail("expected '{' after struct")
        opening = self.expect_text('{')
        self.finish_line()
        fields, methods = [], []
        while self.next_nonempty_line():
            if self.peek().text == '}':
                self.eat()
                self.finish_line()
                if not fields:
                    error_at(opening.line, opening.col, 'a struct must have at least one field')
                node = StructNode(name, fields)
                node.methods = methods
                return node
            if self.peek().text == 'fn':
                if not fields:
                    self.fail('member function must follow at least one field')
                method = self.parse_function(MemberFnNode)
                methods.append(method)
                continue
            if methods:
                self.fail('field must precede member functions')
            typ = self.parse_type()
            mutable = self.peek() is not None and self.peek().text == 'mut'
            if mutable:
                self.eat()
            field = self.expect_kind('identifier', 'a field name')
            fields.append(FieldDeclNode(field.line, field.col, field.text, typ.text, mutable, None))
            self.finish_line()
        error_at(opening.line, opening.col, "'{' is never closed")

    def parse_function(self, node_class=FunctionNode):
        self.eat()
        name = self.expect_kind('identifier', 'a function name')
        self.expect_text(':=')
        self.expect_text('(')
        params = []
        if self.peek() is None or self.peek().text != ')':
            while True:
                typ = self.parse_type()
                param = self.expect_kind('identifier', 'a parameter name')
                params.append(FieldDeclNode(param.line, param.col, param.text, typ.text, False, None))
                if self.peek() is None or self.peek().text != ',':
                    break
                self.eat()
        self.expect_text(')')
        self.expect_text('->')
        result = self.parse_type().text
        self.finish_line()
        body = self.block_after('fn')
        if body.exit is None:
            error_at(name.line, name.col, 'function body must end with exit')
        return node_class(name, params, result, body)

    def parse_program(self):
        structs, functions, statements = [], [], []
        phase, exit_node = 0, None
        while self.next_nonempty_line():
            token = self.peek()
            if exit_node is not None:
                self.fail('statement after exit', token)
            if token.text == 'else':
                self.fail("'else' without an 'if'", token)
            if token.text == 'struct':
                if phase:
                    self.fail('struct must precede functions and statements', token)
                structs.append(self.parse_struct())
            elif token.text == 'fn':
                if phase > 1:
                    self.fail('function must precede statements', token)
                phase = 1
                functions.append(self.parse_function())
            elif token.text == 'exit':
                exit_node = self.parse_exit()
                self.finish_line()
            else:
                phase = 2
                statement = self.parse_statement()
                statements.append(statement)
                if not isinstance(statement, (IfNode, WhileNode)):
                    self.finish_line()
        if exit_node is None:
            self.fail('program has no exit')
        tree = ProgramNode(1, 1, structs + functions + statements, exit_node)
        return tree

    def parse_statement(self):
        token = self.peek()
        if token.text == 'print':
            self.eat()
            self.expect_text('(')
            if self.peek() and self.peek().kind == 'string':
                value = StringNode(self.eat())
            else:
                value = self.parse_expr()
            self.expect_text(')')
            return PrintNode(token, value)
        if token.text in ('struct', 'fn'):
            self.fail('structs and functions are allowed only at top level', token)
        if token.kind == 'identifier' and self.pos + 1 < len(self.toks):
            following = self.toks[self.pos + 1]
            if following.kind == 'identifier' or following.text == 'mut':
                return self.parse_decl()
        return super().parse_statement()

    def parse_init(self):
        opening = self.expect_text('{')
        values = []
        if self.peek() is None or self.peek().text != '}':
            while True:
                values.append(self.parse_init() if self.peek() and self.peek().text == '{' else self.parse_expr())
                if self.peek() is None or self.peek().text != ',':
                    break
                self.eat()
        self.expect_text('}')
        return InitNode(opening, values)

    def parse_decl(self):
        typ = self.parse_type()
        mutable = self.peek() is not None and self.peek().text == 'mut'
        if mutable:
            self.eat()
        name = self.expect_kind('identifier', 'a variable name')
        if self.peek() is None or self.peek().text != '{':
            self.fail(f"variable '{name.text}' needs an initialiser in {{}}", self.peek() or name)
        init = self.parse_init()
        # Preserve the established scalar AST snapshots and diagnostics.
        if typ.text in LLVM_TYPES and len(init.values) == 1 and not isinstance(init.values[0], InitNode):
            init = init.values[0]
        return DeclNode(name.line, name.col, name.text, typ.text, mutable, init)

    def parse_chain(self, token):
        node = VarNode(token.line, token.col, token.text)
        if self.peek() is not None and self.peek().text == '(':
            node = CallNode(token, self.parse_args())
        while self.peek() is not None and self.peek().text == '.':
            dot = self.eat()
            name = self.expect_kind('identifier', 'a field name')
            if self.peek() is not None and self.peek().text == '(':
                node = MemberCallNode(node, name, self.parse_args())
            else:
                node = FieldNode(node, name)
            node.dot = dot
        return node

    def parse_args(self):
        self.expect_text('(')
        args = []
        if self.peek() is None or self.peek().text != ')':
            while True:
                args.append(self.parse_expr())
                if self.peek() is None or self.peek().text != ',':
                    break
                self.eat()
        self.expect_text(')')
        return args

    def parse_assign(self):
        name = self.expect_kind('identifier', 'a variable name')
        if self.peek() is not None and self.peek().text == '(':
            # Global call statements were already rejected in Practice 6.
            self.fail(f"expected ':=' after '{name.text}', got '('")
        target = self.parse_chain(name)
        token = self.peek()
        if token is None:
            self.fail(f"expected ':=' after '{name.text}', found end of line")
        if token.text != ':=':
            self.fail(f"expected ':=' after '{name.text}', got {token.text!r}", token)
        self.eat()
        node = AssignNode(name.line, name.col, name.text, self.parse_expr())
        node.target = target
        return node

    def parse_factor(self):
        token = self.peek()
        if token is not None and token.kind == 'identifier':
            self.eat()
            return self.parse_chain(token)
        return super().parse_factor()


class SemanticChecker(CoreSemanticChecker):
    def __init__(self):
        super().__init__()
        self.structs, self.functions = {}, {}
        self.result = None
        self.owner = self.current = None
        self.pending_calls = []

    def reserved(self, node):
        if node.name in ('read', 'print'):
            self.fail(node, f"name '{node.name}' is reserved")

    def resolve(self, node, name):
        for frame in reversed(self.scopes):
            if name in frame:
                return frame[name]
        if self.owner:
            for field in self.owner.fields:
                if field.name == name:
                    return field
        return super().resolve(node, name)

    def require_type(self, typ, node):
        if typ not in LLVM_TYPES and typ not in self.structs:
            self.fail(node, f"unknown type '{typ}' (struct types must be declared earlier)")

    def visit_program(self, node):
        for item in node.statements:
            if isinstance(item, StructNode):
                self.reserved(item)
                if item.name in self.structs:
                    self.fail(item, f"struct '{item.name}' is already declared")
                names = set()
                for field in item.fields:
                    self.reserved(field)
                    self.require_type(field.type_name, field)
                    if field.name in names:
                        self.fail(field, f"duplicate field '{field.name}'")
                    names.add(field.name)
                self.structs[item.name] = item
                item.method_table = {}
                for method in item.methods:
                    self.reserved(method)
                    if method.name in names:
                        self.fail(method, f"duplicate member '{method.name}'")
                    names.add(method.name)
                    method.owner = item
                    method.mutating = False
                    method.dependencies = set()
                    item.method_table[method.name] = method
            elif isinstance(item, FunctionNode):
                self.reserved(item)
                if item.name in self.functions:
                    self.fail(item, f"function '{item.name}' is already declared")
                self.require_type(item.result, item)
                for param in item.params:
                    self.require_type(param.type_name, param)
                self.functions[item.name] = item
        methods = [m for s in self.structs.values() for m in s.methods]
        for function in list(self.functions.values()) + methods:
            self.owner = getattr(function, 'owner', None)
            self.current = function
            self.require_type(function.result, function)
            self.scopes = [{}]
            self.result = function.result
            for param in function.params:
                self.reserved(param)
                self.require_type(param.type_name, param)
                if param.name in self.scopes[0]:
                    self.fail(param, f"duplicate parameter '{param.name}'")
                self.scopes[0][param.name] = param
            # Parameters and outermost function locals share one scope.
            for statement in function.body.statements:
                self.visit(statement)
            self.visit(function.body.exit)
        self.scopes, self.result = [{}], None
        self.owner = self.current = None
        for item in node.statements:
            if not isinstance(item, (StructNode, FunctionNode)):
                self.visit(item)
        self.visit(node.exit)
        changed = True
        while changed:
            changed = False
            for method in methods:
                if not method.mutating and any(m.mutating for m in method.dependencies):
                    method.mutating = changed = True
        for call in self.pending_calls:
            if call.function.mutating:
                self.check_mutable(call.base)

    def rooted_in_self(self, node):
        while isinstance(node, FieldNode):
            node = node.base
        return isinstance(node, VarNode) and getattr(node, 'implicit_field', False)

    def check_mutable(self, node):
        if isinstance(node, CallNode):
            return  # A call owns a fresh temporary, including its field paths.
        if isinstance(node, FieldNode):
            root = node
            while isinstance(root, FieldNode):
                root = root.base
            if isinstance(root, CallNode):
                return
            if not node.field.mutable:
                self.fail(node, f"cannot write through const field '{node.name}'")
            self.check_mutable(node.base)
        elif not node.decl.mutable:
            self.fail(node, f"cannot assign to '{node.name}': it is not mut")

    def visit_var(self, node):
        result = super().visit_var(node)
        node.implicit_field = self.owner is not None and any(node.decl is f for f in self.owner.fields)
        if node.implicit_field:
            node.index = self.owner.fields.index(node.decl)
        return result

    def visit_print(self, node):
        if not isinstance(node.value, StringNode):
            self.visit(node.value)

    def check_init(self, node, typ):
        self.require_type(typ, node)
        node.type = typ
        if typ in LLVM_TYPES:
            self.fail(node, f"braced field initialisation requires a struct, got {typ}")
        fields = self.structs[typ].fields
        if len(node.values) == 1 and not isinstance(node.values[0], InitNode):
            self.visit(node.values[0])
            if node.values[0].type == typ:
                node.copy = True
                return
        if len(node.values) != len(fields):
            self.fail(node, f"struct '{typ}' needs {len(fields)} values, got {len(node.values)}")
        node.copy = False
        for value, field in zip(node.values, fields):
            if isinstance(value, InitNode):
                self.check_init(value, field.type_name)
            else:
                self.visit(value)
            self.check_assignable(value, field.type_name, value, f"initialise field '{field.name}'")

    def visit_decl(self, node):
        self.reserved(node)
        self.require_type(node.type_name, node)
        if isinstance(node.init, InitNode):
            self.check_init(node.init, node.type_name)
        super().visit_decl(node)

    def visit_init(self, node):
        return node.type

    def visit_field(self, node):
        typ = self.visit(node.base)
        struct = self.structs.get(typ)
        if struct is None:
            self.fail(getattr(node, 'dot', node), f"type '{typ}' has no fields")
        for index, field in enumerate(struct.fields):
            if field.name == node.name:
                node.index, node.field, node.type = index, field, field.type_name
                return node.type
        self.fail(node, f"struct '{typ}' has no field '{node.name}'")

    def all_mut(self, typ):
        return typ in LLVM_TYPES or all(f.mutable and self.all_mut(f.type_name) for f in self.structs[typ].fields)

    def visit_assign(self, node):
        root = node.target
        while isinstance(root, FieldNode):
            root = root.base
        if isinstance(root, CallNode):
            self.fail(root, 'cannot assign to a call result')
        if self.owner:
            self.visit(node.target)
            if self.rooted_in_self(node.target):
                self.check_mutable(node.target)
                if not self.all_mut(node.target.type):
                    self.fail(node, 'whole-object assignment requires every field at every depth to be mut')
                self.current.mutating = True
                self.visit(node.value)
                self.check_assignable(node.value, node.target.type, node, 'assign to field')
                node.implicit_assignment = True
                return
        if isinstance(node.target, VarNode):
            super().visit_assign(node)
            if not self.all_mut(node.decl.type_name):
                self.fail(node, 'whole-object assignment requires every field at every depth to be mut')
            return
        typ = self.visit(node.target)
        current = node.target
        while isinstance(current, FieldNode):
            if not current.field.mutable:
                self.fail(current, f"cannot write through const field '{current.name}'")
            current = current.base
        if not current.decl.mutable:
            self.fail(current, f"cannot assign to '{current.name}': it is not mut")
        if not self.all_mut(typ):
            self.fail(node.target, 'whole-object assignment requires every field at every depth to be mut')
        self.visit(node.value)
        self.check_assignable(node.value, typ, node, 'assign to field')

    def visit_call(self, node):
        if node.name == 'print':
            self.fail(node, 'print has no value')
        if node.name == 'read':
            if node.args:
                self.fail(node, 'read needs 0 arguments')
            node.type = 'i32'
            return node.type
        if self.owner and node.name in self.owner.method_table:
            node.function = self.owner.method_table[node.name]
            node.implicit_member = True
            self.current.dependencies.add(node.function)
            return self.check_arguments(node, node.function)
        function = self.functions.get(node.name)
        if function is None:
            self.fail(node, f"unknown function '{node.name}'")
        return self.check_arguments(node, function)

    def visit_membercall(self, node):
        if node.name in ('read', 'print'):
            self.fail(node, f"name '{node.name}' is reserved")
        typ = self.visit(node.base)
        struct = self.structs.get(typ)
        if struct is None:
            self.fail(getattr(node, 'dot', node), f"type '{typ}' has no member functions")
        function = struct.method_table.get(node.name)
        if function is None:
            self.fail(node, f"struct '{typ}' has no member function '{node.name}'")
        self.pending_calls.append(node)
        if self.owner and self.rooted_in_self(node.base):
            self.current.dependencies.add(function)
        return self.check_arguments(node, function)

    def check_arguments(self, node, function):
        if len(node.args) != len(function.params):
            self.fail(node, f"function '{node.name}' needs {len(function.params)} arguments, got {len(node.args)}")
        for arg, param in zip(node.args, function.params):
            self.visit(arg)
            self.check_assignable(arg, param.type_name, arg, f"pass argument '{param.name}'")
        node.function, node.type = function, function.result
        return node.type

    def visit_exit(self, node):
        self.visit(node.value)
        if self.result is None:
            if node.value.type not in LLVM_TYPES:
                self.fail(node, 'top-level exit requires a built-in type')
        elif node.value.type != self.result:
            self.fail(node, f"function exit must have type {self.result}, got {node.value.type}")


class CodeGen(CoreCodeGen):
    def __init__(self):
        super().__init__()
        self.types = dict(LLVM_TYPES)
        self.in_function = False

    def visit_program(self, node):
        main_builder = self.builder
        self.structs = {s.name: s for s in node.statements if isinstance(s, StructNode)}
        for item in node.statements:
            if isinstance(item, StructNode):
                typ = self.module.context.get_identified_type(item.name)
                typ.set_body(*(self.types[f.type_name] for f in item.fields))
                self.types[item.name] = typ
            elif isinstance(item, FunctionNode):
                item.llvm = ir.Function(self.module, ir.FunctionType(self.types[item.result], [self.types[p.type_name] for p in item.params]), name='user.' + item.name)
        methods = [m for s in self.structs.values() for m in s.methods]
        for method in methods:
            # Preserve the teacher's Point_shift spelling while disambiguating
            # A_b.c versus A.b_c. Global user functions use a separate namespace.
            name = method.owner.name + '_' + method.name
            if name in self.module.globals:
                name = self.module.get_unique_name(name)
            signature = ir.FunctionType(
                self.types[method.result],
                [self.types[method.owner.name].as_pointer()]
                + [self.types[p.type_name] for p in method.params],
            )
            method.llvm = ir.Function(self.module, signature, name=name)
        for item in list(node.statements) + methods:
            if isinstance(item, FunctionNode):
                self.builder = ir.IRBuilder(item.llvm.append_basic_block('entry'))
                self.in_function = True
                arguments = list(item.llvm.args)
                if isinstance(item, MemberFnNode):
                    self.this = arguments.pop(0)
                    self.this.name = 'this'
                for param, argument in zip(item.params, arguments):
                    argument.name = param.name
                    param.ptr = self.alloca_in_entry(self.types[param.type_name], param.name + '.slot')
                    self.builder.store(argument, param.ptr)
                self.visit(item.body)
        self.builder, self.in_function = main_builder, False
        for item in node.statements:
            if not isinstance(item, (StructNode, FunctionNode)):
                self.visit(item)
        self.visit(node.exit)
        return self.module

    def visit_decl(self, node):
        value = self.coerce(self.visit(node.init), node.init.type, node.type_name)
        node.ptr = self.alloca_in_entry(self.types[node.type_name], node.name)
        self.builder.store(value, node.ptr)

    def visit_init(self, node):
        if node.copy:
            return self.visit(node.values[0])
        typ = self.types[node.type]
        result = ir.Constant(typ, ir.Undefined)
        for index, value in enumerate(node.values):
            field_type = typ.elements[index]
            emitted = self.visit(value)
            if emitted.type != field_type:
                emitted = self.builder.sext(emitted, field_type)
            result = self.builder.insert_value(result, emitted, index)
        return result

    def field_ptr(self, node):
        if isinstance(node, VarNode):
            if getattr(node, 'implicit_field', False):
                return self.builder.gep(self.this, [ir.Constant(I32, 0), ir.Constant(I32, node.index)], inbounds=True)
            return node.decl.ptr
        if isinstance(node, CallNode):
            value = self.visit(node)
            slot = self.alloca_in_entry(value.type, 'temporary')
            self.builder.store(value, slot)
            return slot
        return self.builder.gep(self.field_ptr(node.base), [ir.Constant(I32, 0), ir.Constant(I32, node.index)], inbounds=True)

    def visit_field(self, node):
        root = node
        while isinstance(root, FieldNode):
            root = root.base
        if isinstance(root, VarNode):
            return self.builder.load(self.field_ptr(node))
        return self.builder.extract_value(self.visit(node.base), node.index)

    def visit_var(self, node):
        return self.builder.load(self.field_ptr(node))

    def visit_assign(self, node):
        if isinstance(node.target, VarNode) and not getattr(node, 'implicit_assignment', False):
            return super().visit_assign(node)
        value = self.coerce(self.visit(node.value), node.value.type, node.target.type)
        self.builder.store(value, self.field_ptr(node.target))

    def visit_call(self, node):
        if node.name == 'read':
            if 'scanf' not in self.module.globals:
                ir.Function(self.module, ir.FunctionType(I32, [I8.as_pointer()], var_arg=True), name='scanf')
            slot = self.alloca_in_entry(I32, 'read.slot')
            self.builder.store(ir.Constant(I32, 0), slot)
            self.builder.call(self.module.globals['scanf'], [self.text_ptr(b'%d'), slot])
            return self.builder.load(slot)
        args = [self.coerce(self.visit(arg), arg.type, param.type_name) for arg, param in zip(node.args, node.function.params)]
        if getattr(node, 'implicit_member', False):
            args.insert(0, self.this)
        return self.builder.call(node.function.llvm, args)

    def visit_membercall(self, node):
        address = self.field_ptr(node.base)
        args = [self.coerce(self.visit(arg), arg.type, param.type_name) for arg, param in zip(node.args, node.function.params)]
        return self.builder.call(node.function.llvm, [address] + args)

    def text_ptr(self, data):
        cache = getattr(self, 'texts', None)
        if cache is None:
            self.texts = cache = {}
        if data not in cache:
            raw = bytearray(data + b'\0')
            glob = ir.GlobalVariable(self.module, ir.ArrayType(I8, len(raw)), name='text.' + str(len(cache)))
            glob.linkage, glob.global_constant = 'private', True
            glob.initializer = ir.Constant(glob.type.pointee, raw)
            cache[data] = glob
        return self.builder.bitcast(cache[data], I8.as_pointer())

    def output_text(self, data):
        self.builder.call(self.printf, [self.text_ptr(b'%s'), self.text_ptr(data)])

    def print_value(self, value, typ):
        if typ in self.structs:
            self.output_text((typ + '{').encode())
            slot = self.alloca_in_entry(value.type, 'print.object')
            self.builder.store(value, slot)
            for index, field in enumerate(self.structs[typ].fields):
                self.output_text(((', ' if index else '') + field.name + ': ').encode())
                ptr = self.builder.gep(slot, [ir.Constant(I32, 0), ir.Constant(I32, index)], inbounds=True)
                self.print_value(self.builder.load(ptr), field.type_name)
            self.output_text(b'}')
        else:
            fmt = b'%d' if typ == 'i32' else b'%lld'
            if typ == 'bool':
                fmt = b'%s'
                value = self.builder.select(value, self.text_ptr(b'true'), self.text_ptr(b'false'))
            self.builder.call(self.printf, [self.text_ptr(fmt), value])

    def visit_print(self, node):
        if isinstance(node.value, StringNode):
            self.output_text(node.value.value.encode('latin1'))
        else:
            self.print_value(self.visit(node.value), node.value.type)
        self.output_text(b'\n')

    def visit_exit(self, node):
        if self.in_function:
            self.builder.ret(self.visit(node.value))
        else:
            super().visit_exit(node)


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
