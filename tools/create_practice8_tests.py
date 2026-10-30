"""Explicit fixture authoring; never called by the test runner.

Runtime expectations below are calculated from the language rules, not execution.
Error fragments are asserted before recording full source-location snapshots.
"""
import contextlib
import io
from pathlib import Path
import sys
import textwrap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.compiler import Parser, SemanticChecker, CompileError, lex, check_with_parse_tree


def clean(source):
    return textwrap.dedent(source).strip() + '\n'


SCALE = clean('''
struct Scale
{
 i32 k
 fn call := (i32 v) -> i32
 {
  i32 r{v * k}
  exit r
 }
}
''')
COUNTER = clean('''
struct Counter
{
 i32 mut n
 fn call := () -> i32
 {
  n := n + 1
  exit n
 }
}
''')
SQ = clean('''
fn sq := (i32 v) -> i32
{
 i32 r{v * v}
 exit r
}
''')
TASK1 = SCALE + COUNTER + clean('''
struct Shape
{
 Scale scale
 i32 side
 fn grown := () -> i32
 {
  i32 g{scale(side)}
  exit g
 }
}
Scale triple{3}
Counter mut c{0}
Shape s{{2}, 5}
print(triple(14))
print(triple.call(14))
print(s.scale(7))
print(s.grown())
i32 a{c()}
i32 b{c()}
print(c)
i32 r{a * 10 + b}
exit r
''')
TASK2 = SQ + clean('''
fn sum_scaled := (i32 factor, i32 a, i32 b) -> i32
{
 fn times := [factor](i32 v) -> i32
 {
  i32 r{factor * sq(v)}
  exit r
 }
 i32 s{times(a) + times(b)}
 exit s
}
i32 mut k{10}
fn add_k := [k](i32 y) -> i32
{
 i32 r{k + y}
 exit r
}
k := 100
print(add_k(5))
print(k)
print(sum_scaled(2, 3, 4))
exit add_k(1)
''')
BONUS = clean('''
i32 n{0}
fn next := [mut n]() -> i32
{
 n := n + 1
 exit n
}
print(next())
print(next())
fn twice := [mut next]() -> i32
{
 i32 a{next()}
 i32 b{next()}
 i32 r{a * 10 + b}
 exit r
}
print(twice())
print(next())
exit n
''')

ok = {
 'task1': (TASK1, '42\n42\n14\n10\nCounter{n: 2}\nProgram exit with result 12\n'),
 'task2': (TASK2, '15\n100\n50\nProgram exit with result 11\n'),
 'bonus': (BONUS, '1\n2\n34\n3\nProgram exit with result 0\n'),
 'empty_global': (SQ + clean('''
fn square := [](i32 x) -> i32
{
 exit sq(x)
}
print(square(9))
exit square.call(4)
'''), '81\nProgram exit with result 16\n'),
 'loop': (clean('''
i32 mut i{0}
while i != 3
{
 fn value := [mut i]() -> i32
 {
  i := i + 10
  exit i
 }
 print(value())
 print(value())
 i := i + 1
}
exit i
'''), '10\n20\n11\n21\n12\n22\nProgram exit with result 3\n'),
 'copies_mixed': (clean('''
i32 n{5}
i32 step{2}
fn first := [mut n, step]() -> i32
{
 n := n + step
 exit n
}
fn second := [mut n]() -> i32
{
 n := n + 1
 exit n
}
print(first())
print(first())
print(second())
print(n)
exit second()
'''), '7\n9\n6\n5\nProgram exit with result 7\n'),
 'nested': (clean('''
i32 k{3}
fn outer := [k](i32 v) -> i32
{
 fn inner := [k, v]() -> i32
 {
  i32 r{k + v}
  exit r
 }
 exit inner()
}
fn copy := [outer]() -> i32
{
 exit outer(4)
}
exit copy()
'''), 'Program exit with result 7\n'),
 'member_capture': (clean('''
struct Box
{
 i32 x
 fn run := () -> i32
 {
  fn read_x := [x]() -> i32
  {
   exit x
  }
  exit read_x()
 }
}
Box b{17}
exit b.run()
'''), 'Program exit with result 17\n'),
 'same_name_scopes': (clean('''
i32 n{2}
if true
{
 fn value := [n]() -> i32
 {
  exit n
 }
 print(value())
}
if true
{
 fn value := [](i32 x) -> i32
 {
  exit x
 }
 print(value(8))
}
exit 0
'''), '2\n8\nProgram exit with result 0\n'),
 'mut_callable_field': (COUNTER + clean('''
struct Holder
{
 Counter mut counter
 fn call := () -> i32
 {
  exit counter()
 }
}
Holder mut h{{0}}
print(h.counter())
print(h())
exit h.counter.call()
'''), '1\n2\nProgram exit with result 3\n'),
 'capture_read': (clean('''
i32 n{read()}
fn get := [n]() -> i32
{
 exit n
}
print(get())
exit get()
'''), '13\nProgram exit with result 13\n'),
 'loop_const': (clean('''
i32 mut i{0}
while i != 3
{
 fn get := [i]() -> i32
 {
  exit i
 }
 i := i + 1
 print(get())
}
exit i
'''), '0\n1\n2\nProgram exit with result 3\n'),
 'global_call_name': (clean('''
fn call := () -> i32
{
 exit 23
}
fn get := []() -> i32
{
 exit call()
}
exit get()
'''), 'Program exit with result 23\n'),
 'struct_copy': (SCALE + clean('''
Scale mut original{2}
fn get := [original](i32 n) -> i32
{
 exit original(n)
}
print(get(3))
exit get(4)
'''), '6\nProgram exit with result 8\n'),
 'types': (clean('''
i64 wide{2147483648}
bool flag{true}
fn get := [wide, flag](i32 n) -> i64
{
 if flag
 {
  i64 value{wide + n}
  exit value
 }
 exit wide
}
print(get(2))
exit 0
'''), '2147483650\nProgram exit with result 0\n'),
}

simple = clean('''
i32 mut k{10}
fn add := [k](i32 y) -> i32
{
 i32 r{k + y}
 exit r
}
exit add(1)
''')
err = {
 'no_call': ('struct Point\n{\n i32 x\n}\nPoint p{1}\nexit p()\n', 'has no member function'),
 'scalar': ('i32 n{1}\nexit n()\n', 'it is i32'),
 'ambiguous': (SQ + 'i32 sq{1}\nexit sq(2)\n', 'both a variable and a function'),
 'arity': (SCALE + 'Scale t{2}\nexit t()\n', "function 't' needs 1 arguments"),
 'type': (SCALE + 'Scale t{2}\nexit t(true)\n', 'pass argument'),
 'const_callable': (COUNTER + 'Counter c{0}\nexit c()\n', "cannot call 'c'"),
 'const_callable_field': (COUNTER + 'struct Box\n{\n Counter c\n}\nBox mut b{{0}}\nexit b.c()\n', "cannot call 'c'"),
 'missing': (simple.replace('[k]', '[]'), 'not captured'),
 'const_capture': (simple.replace('i32 r{k + y}', 'k := k + y\n i32 r{k}'), 'write [mut k]'),
 'duplicate': (simple.replace('[k]', '[k, k]'), 'captured twice'),
 'unknown_capture': (simple.replace('[k]', '[unknown]'), 'no variable'),
 'param_capture': (simple.replace('(i32 y)', '(i32 k)'), 'conflicts with a capture'),
 'self': ('fn self := []() -> i32\n{\n exit self()\n}\nexit 0\n', "unknown function 'self'"),
 'argument': (SQ + simple.replace('exit add(1)', 'exit sq(add)'), "passed to 'sq'"),
 'exit': (simple.replace('exit add(1)', 'exit add'), 'returned by exit'),
 'decl': (simple.replace('exit add(1)', 'i32 x{add}\nexit 0'), 'initialise'),
 'assign': (simple.replace('exit add(1)', 'k := add\nexit 0'), 'assign'),
 'print': (simple.replace('exit add(1)', 'print(add)\nexit 0'), 'printed'),
 'private_field': (simple.replace('exit add(1)', 'exit add.k'), 'accessed through a field'),
 'const_nested': (BONUS.replace('[mut next]', '[next]'), "cannot call 'next'"),
 'uncaptured_outer_param': ('fn f := (i32 p) -> i32\n{\n fn g := []() -> i32\n {\n  exit p\n }\n exit g()\n}\nexit f(1)\n', 'not captured'),
 'uncaptured_field': ('struct Box\n{\n i32 x\n fn f := () -> i32\n {\n  fn g := []() -> i32\n  {\n   exit x\n  }\n  exit g()\n }\n}\nexit 0\n', 'not captured'),
 'nested_function': ('if true\n{\n fn f := () -> i32\n {\n  exit 0\n }\n}\nexit 0\n', 'allowed only at top level'),
 'member_capture_list': ('struct Box\n{\n i32 x\n fn f := [x]() -> i32\n {\n  exit x\n }\n}\nexit 0\n', 'cannot have a capture list'),
 'top_not_visible': ('fn f := () -> i32\n{\n fn g := [k]() -> i32\n {\n  exit k\n }\n exit g()\n}\ni32 k{1}\nexit f()\n', 'no variable'),
 'struct_init': ('struct Box\n{\n i32 x\n}\n' + simple.replace('exit add(1)', 'Box b{add}\nexit 0'), 'initialise'),
 'duplicate_local': (simple.replace('exit add(1)', 'i32 add{1}\nexit 0'), 'already declared'),
 'duplicate_lambda': ('i32 add{1}\n' + simple, 'already declared'),
 'generated_call_hidden': ('fn f := []() -> i32\n{\n exit call()\n}\nexit f()\n', "unknown function 'call'"),
 'member_not_inherited': ('struct Box\n{\n i32 x\n fn helper := () -> i32\n {\n  exit x\n }\n fn f := () -> i32\n {\n  fn g := []() -> i32\n  {\n   exit helper()\n  }\n  exit g()\n }\n}\nexit 0\n', "unknown function 'helper'"),
 'mut_capture_const_field': ('struct Box\n{\n i32 x\n}\nBox b{1}\nfn change := [mut b]() -> i32\n{\n b.x := 2\n exit b.x\n}\nexit change()\n', 'const field'),
}

for name, (source, expected) in ok.items():
    path = Path('tests/ok') / f'p8_{name}.txt'
    path.write_text(source, encoding='utf-8', newline='\n')
    tree = Parser(lex(source.encode())).parse_program()
    parsed = check_with_parse_tree(tree)
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        parsed.dump()
    path.with_suffix('.ast').write_text(stream.getvalue(), encoding='utf-8', newline='\n')
    checked = io.StringIO()
    with contextlib.redirect_stdout(checked):
        tree.dump()
    path.with_suffix('.checked').write_text(checked.getvalue(), encoding='utf-8', newline='\n')
    path.with_suffix('.expected').write_text(expected, encoding='utf-8', newline='\n')
Path('tests/ok/p8_capture_read.in').write_text('13\n', encoding='utf-8', newline='\n')
for name, (source, fragment) in err.items():
    path = Path('tests/err') / f'p8_{name}.txt'
    path.write_text(source, encoding='utf-8', newline='\n')
    try:
        tree = Parser(lex(source.encode())).parse_program()
        SemanticChecker().visit(tree)
    except CompileError as error:
        assert fragment in str(error), (name, fragment, str(error))
        path.with_suffix('.expected').write_text(f'compilation error: {error}\n', encoding='utf-8', newline='\n')
    else:
        raise AssertionError(f'accepted {name}')
print(f'Authored {len(ok)} positive and {len(err)} negative Practice 8 fixtures')
