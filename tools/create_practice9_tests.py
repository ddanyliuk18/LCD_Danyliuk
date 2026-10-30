"""Explicit fixture authoring, never invoked by verification.

Stdout is specified independently. Tree assertions and round counts validate
the intended removals before authoring checked-tree snapshots.
"""
import contextlib
import io
from pathlib import Path
import sys
import textwrap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.compiler import Parser, SemanticChecker, lex
from src.optimization import UnusedRemover


def clean(source):
    return textwrap.dedent(source).strip() + '\n'


CHAIN = clean('''
fn twice := (i32 a) -> i32
{
 i32 r{a + a}
 exit r
}
fn helper := (i32 a) -> i32
{
 exit twice(a)
}
fn unused := () -> i32
{
 exit helper(1)
}
exit twice(2)
''')
BONUS = clean('''
fn square := (i32 a) -> i32
{
 i32 r{a * a}
 exit r
}
fn quiet := (i32 a) -> i32
{
 exit square(a)
}
fn loud := (i32 a) -> i32
{
 print(a)
 exit a
}
i32 a{square(3)}
i32 b{quiet(4)}
i32 c{loud(5)}
exit 0
''')
COUNTER = clean('''
struct Counter
{
 i32 mut n
 fn bump := () -> i32
 {
  n := n + 1
  exit n
 }
 fn peek := () -> i32
 {
  exit n
 }
}
''')

# name: (source, expected stdout, required AST fragments, forbidden fragments)
cases = {
 'warmup_chain': ('i32 x{10}\ni32 y{x}\ni32 z{15}\nexit z\n',
     'Program exit with result 15\n', ['Decl z'], ['Decl x', 'Decl y']),
 'warmup_shadow': (clean('''
i32 mut r{0}
i32 x{1}
if true
{
 i32 x{10}
 r := x
}
exit r
'''), 'Program exit with result 10\n', ['Decl x', 'Const 10', 'Assign r'], ['Const 1\n']),
 'function_chain': (CHAIN, 'Program exit with result 4\n', ['Function twice'], ['Function helper', 'Function unused']),
 'empty_if': (clean('''
fn condition := () -> bool
{
 print(7)
 exit true
}
if condition()
{
 i32 gone{2}
}
else
{
 i32 other{3}
}
exit 0
'''), '7\nProgram exit with result 0\n', ['If', 'Block', 'Call condition'], ['Decl gone', 'Decl other']),
 'printing_initializer': (clean('''
fn loud := () -> i32
{
 print(9)
 exit 1
}
i32 unread{loud()}
exit 0
'''), '9\nProgram exit with result 0\n', ['Decl unread', 'Function loud'], []),
 'nothing_removed': ('i32 n{4}\nprint(n)\nexit n\n', '4\nProgram exit with result 4\n', ['Decl n', 'Print', 'Exit'], []),
 'bonus_pure': (BONUS, '5\nProgram exit with result 0\n', ['Function loud', 'Decl c'], ['Function quiet', 'Function square', 'Decl a', 'Decl b']),
 'bonus_counter': (COUNTER + clean('''
Counter mut c{0}
i32 t{c.bump()}
i32 u{c.peek()}
print(c)
exit 0
'''), 'Counter{n: 1}\nProgram exit with result 0\n', ['Decl t', 'MemberFn peek', 'MemberFn bump'], ['Decl u']),
 'bonus_relay': (clean('''
fn relay := () -> i32
{
 exit loud()
}
fn loud := () -> i32
{
 print(8)
 exit 1
}
i32 unused{relay()}
exit 0
'''), '8\nProgram exit with result 0\n', ['Function relay', 'Function loud', 'Decl unused'], []),
 'bonus_while': (clean('''
fn maybe := () -> i32
{
 while false
 {
  i32 gone{1}
 }
 exit 2
}
i32 unused{maybe()}
exit 0
'''), 'Program exit with result 0\n', ['Function maybe', 'Decl unused', 'While'], ['Decl gone']),
 'bonus_recursive': (clean('''
fn recurse := (i32 n) -> i32
{
 if n == 0
 {
  exit 1
 }
 i32 smaller{n - 1}
 exit recurse(smaller)
}
i32 unused{recurse(2)}
exit 0
'''), 'Program exit with result 0\n', ['Function recurse', 'Decl unused'], []),
 'bonus_lambdas': (clean('''
i32 k{3}
fn loud := [k]() -> i32
{
 print(k)
 exit k
}
fn quiet := [k]() -> i32
{
 exit k
}
i32 a{loud()}
i32 b{quiet()}
exit 0
'''), '3\nProgram exit with result 0\n', ['Lambda loud', 'Lambda quiet', 'Decl a', 'Decl k'], ['Decl b']),
 'dead_assignments': (clean('''
struct Point
{
 i32 mut x
}
Point mut p{1}
p.x := 2
i32 mut y{3}
y := 4
exit 0
'''), 'Program exit with result 0\n', ['Struct Point'], ['Decl p', 'Decl y', 'Assign']),
 'assignment_effect': (clean('''
fn loud := () -> i32
{
 print(6)
 exit 2
}
i32 mut y{0}
y := loud()
exit 0
'''), '6\nProgram exit with result 0\n', ['Decl y', 'Assign y', 'Call loud'], []),
 'field_assignment_effect': (COUNTER + clean('''
Counter mut c{0}
c.n := read()
exit 0
'''), 'Program exit with result 0\n', ['Decl c', 'Assign c.n', 'Call read'], []),
 'read_initializer': ('i32 unread{read()}\ni32 value{read()}\nprint(value)\nexit 0\n',
     '22\nProgram exit with result 0\n', ['Decl unread', 'Decl value'], []),
 'self_feeding': ('i32 mut k{0}\nk := k + 1\nexit 0\n',
     'Program exit with result 0\n', ['Decl k', 'Assign k'], []),
 'mutual_cycle': (clean('''
fn left := () -> i32
{
 exit right()
}
fn right := () -> i32
{
 exit left()
}
exit 0
'''), 'Program exit with result 0\n', ['Function left', 'Function right'], []),
 'all_body_contexts': (clean('''
struct Box
{
 i32 x
 fn get := () -> i32
 {
  i32 member_dead{2}
  exit x
 }
}
fn helper := (i32 ignored) -> i32
{
 i32 local_dead{3}
 exit 7
}
fn closure := []() -> i32
{
 i32 lambda_dead{4}
 exit helper(5)
}
Box b{1}
print(b.get())
print(closure())
exit 0
'''), '1\n7\nProgram exit with result 0\n', ['Field ignored', 'Lambda closure', 'Function helper'], ['Decl member_dead', 'Decl local_dead', 'Decl lambda_dead']),
 'removed_lambda_registry': (clean('''
fn helper := () -> i32
{
 exit 3
}
fn abandoned := () -> i32
{
 fn closure := []() -> i32
 {
  exit helper()
 }
 exit closure()
}
exit 0
'''), 'Program exit with result 0\n', ['Exit'], ['Function helper', 'Function abandoned', 'Lambda closure']),
 'nested_argument_effect': (clean('''
fn square := (i32 n) -> i32
{
 i32 result{n * n}
 exit result
}
i32 first{square(read())}
i32 second{read()}
print(second)
exit 0
'''), '9\nProgram exit with result 0\n', ['Decl first', 'Function square'], []),
 'callable_effect': (clean('''
struct Printer
{
 i32 n
 fn call := () -> i32
 {
  print(n)
  exit n
 }
}
Printer p{12}
i32 unused{p()}
exit 0
'''), '12\nProgram exit with result 0\n', ['Decl p', 'Decl unused', 'CallableCall p'], []),
 'capture_use': (clean('''
i32 k{4}
fn unused := [k]() -> i32
{
 exit k
}
exit 0
'''), 'Program exit with result 0\n', ['Decl k', 'Lambda unused'], []),
 'loop_condition': (clean('''
i32 mut i{0}
while i != 2
{
 i32 dead{i}
 i := i + 1
}
exit i
'''), 'Program exit with result 2\n', ['Decl i', 'While', 'Assign i'], ['Decl dead']),
 'pure_assignment_chain': (clean('''
fn pure := (i32 n) -> i32
{
 exit n
}
i32 x{1}
i32 mut y{0}
y := pure(x)
exit 0
'''), 'Program exit with result 0\n', ['Exit'], ['Decl x', 'Decl y', 'Assign', 'Function pure']),
 'nested_initializers': (clean('''
struct Point
{
 i32 x
}
struct Box
{
 Point p
 i32 n
}
Box unused{{read()}, 3}
i32 next{read()}
print(next)
exit 0
'''), '8\nProgram exit with result 0\n', ['Decl unused', 'Call read'], []),
}

rounds = {
 'warmup_chain': [(1, 0), (1, 0), (0, 0)],
 'warmup_shadow': [(1, 0), (0, 0)],
 'function_chain': [(0, 1), (0, 1), (0, 0)],
 'bonus_pure': [(2, 0), (0, 1), (0, 1), (0, 0)],
 'nothing_removed': [(0, 0)],
}
inputs = {
 'field_assignment_effect': '17\n', 'read_initializer': '11 22\n',
 'nested_argument_effect': '7 9\n', 'nested_initializers': '5 8\n',
}
Path('tests/opt').mkdir(exist_ok=True)
for name, (source, expected, present, absent) in cases.items():
    tree = Parser(lex(source.encode())).parse_program()
    SemanticChecker().visit(tree)
    optimizer = UnusedRemover()
    optimizer.run(tree)
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        tree.dump()
    ast = stream.getvalue()
    for fragment in present:
        assert fragment in ast, (name, 'missing', fragment, ast)
    for fragment in absent:
        assert fragment not in ast, (name, 'unexpected', fragment, ast)
    if name in rounds:
        assert optimizer.rounds == rounds[name], (name, optimizer.rounds)
    path = Path('tests/opt') / (name + '.txt')
    path.write_text(source, encoding='utf-8', newline='\n')
    path.with_suffix('.astc').write_text(ast, encoding='utf-8', newline='\n')
    path.with_suffix('.expected').write_text(expected, encoding='utf-8', newline='\n')
    if name in inputs:
        path.with_suffix('.in').write_text(inputs[name], encoding='utf-8', newline='\n')
print(f'Authored {len(cases)} optimization fixtures with independent stdout and removal assertions')
