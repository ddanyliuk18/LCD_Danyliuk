"""Author Practice 7 fixtures. Output expectations are hand calculated.
Run only when deliberately updating fixtures; never from the test runner.
"""
from pathlib import Path
import contextlib
import io
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.compiler import Parser, SemanticChecker, CompileError, lex
P = '''struct Point
{
 i32 mut x
 i32 mut y
 fn d2 := () -> i32
 {
  i32 r{x * x + y * y}
  exit r
 }
 fn shift := (i32 dx) -> i32
 {
  x := x + dx
  exit x
 }
 fn moved := (i32 dx) -> Point
 {
  Point q{x + dx, y}
  exit q
 }
 fn add := (i32 a, i32 b) -> i32
 {
  i32 r{x + a + b}
  exit r
 }
 fn twice := () -> i32
 {
  exit add(d2(), d2())
 }
}
'''
C = '''struct Circle
{
 Point center
 i32 radius
 fn area2 := () -> i32
 {
  i32 r{radius * radius * 3}
  exit r
 }
 fn grown := (i32 dr) -> Circle
 {
  Circle g{center, radius + dr}
  exit g
 }
}
'''
cycle = '''struct Cell
{
 i32 mut x
 fn a := (i32 n) -> i32
 {
  if n == 0
  {
   exit x
  }
  exit b(n - 1)
 }
 fn b := (i32 n) -> i32
 {
  x := x + 1
  exit a(n)
 }
}
'''
ok = {
 'task1': (P+C+'''Point mut p{3, 4}
i32 d{p.d2()}
i32 nx{p.shift(2)}
Circle c{p, 2}
i32 a{c.area2()}
i32 cd{c.center.d2()}
i32 result{d + nx + a + cd}
exit result
''', 'Program exit with result 83\n', None),
 'two_args': (P+'Point p{3, 4}\nexit p.add(2, 5)\n', 'Program exit with result 10\n', None),
 'mutation': (P+'Point mut p{3, 4}\ni32 n{p.shift(2)}\nexit p.x\n', 'Program exit with result 5\n', None),
 'implicit': (P+'Point p{3, 4}\nexit p.twice()\n', 'Program exit with result 53\n', None),
 'task3': (P+C+'''Point p{read(), read()}
Circle c{p, 2}
i64 big{3000000000}
print("p and c:")
print(p)
print(c)
print(p.x + p.y)
print(big * 2)
print(p.x == 3)
exit c.radius
''', 'p and c:\nPoint{x: 3, y: 4}\nCircle{center: Point{x: 3, y: 4}, radius: 2}\n7\n6000000000\ntrue\nProgram exit with result 2\n', '3 4\n'),
 'bonus': (P+C+'''fn origin := () -> Point
{
 Point o{0, 0}
 exit o
}
Point p{3, 4}
Circle c{p, 2}
i32 a{p.moved(1).shift(2)}
i32 b{c.grown(3).radius}
i32 d{c.grown(1).center.d2()}
i32 e{origin().moved(7).x}
i32 result{a + b + d + e + p.x}
exit result
''', 'Program exit with result 46\n', None),
 'cycle': (cycle+'Cell mut c{1}\nexit c.a(3)\n', 'Program exit with result 4\n', None),
 'shadow': ('''struct S
{
 i32 x
 fn f := (i32 x) -> i32
 {
  i32 mut y{x}
  y := y + 1
  exit y
 }
 fn g := () -> i32
 {
  i32 mut x{8}
  x := x + 1
  exit x
 }
}
S s{1}
i32 r{s.f(4) + s.g()}
exit r
''', 'Program exit with result 14\n', None),
 'printing': (P+'''fn show := () -> Point
{
 print(false)
 print(0 - 9)
 Point p{1, 2}
 exit p
}
Point p{3, 4}
print(show())
print(p.moved(1))
print("100% \\n")
i32 mut n{0}
while n != 1
{
 print(true)
 n := n + 1
}
if false
{
 print(8)
}
else
{
 print(9)
}
exit read()
''', 'false\n-9\nPoint{x: 1, y: 2}\nPoint{x: 4, y: 4}\n100% \\n\ntrue\n9\nProgram exit with result 7\n', '7\n'),
 'mut_field': (P+'''struct Box
{
 Point mut p
 fn change := () -> i32
 {
  exit p.shift(2)
 }
}
Box mut b{{1, 2}}
i32 n{b.change()}
exit b.p.x
''', 'Program exit with result 3\n', None),
}
err = {
 'field_after': 'struct S\n{\n i32 x\n fn f := () -> i32\n {\n  exit x\n }\n i32 y\n}\nexit 0\n',
 'method_before': 'struct S\n{\n fn f := () -> i32\n {\n  exit 0\n }\n}\nexit 0\n',
 'duplicate': P.replace('fn d2', 'fn x')+'exit 0\n',
 'duplicate_method': P.replace('fn shift', 'fn d2')+'exit 0\n',
 'const_object': P+'Point p{3, 4}\nexit p.shift(1)\n',
 'const_field': P+C+'Circle mut c{{3, 4}, 2}\nexit c.center.shift(1)\n',
 'unknown': P+'Point p{3, 4}\nexit p.unknown()\n',
 'arity': P+'Point p{3, 4}\nexit p.shift()\n',
 'arg_type': P+'Point p{3, 4}\nexit p.shift(true)\n',
 'scalar': 'i32 x{1}\nexit x.f()\n',
 'type_call': P+'exit Point.d2()\n',
 'global': P.replace('exit r', 'exit global', 1)+'i32 global{1}\nexit 0\n',
 'return': P.replace('exit r', 'exit true', 1)+'exit 0\n',
 'const_write': P.replace('i32 mut x', 'i32 x')+'exit 0\n',
 'cycle_const': cycle+'Cell c{1}\nexit c.a(3)\n',
 'string_value': 'i32 x{"hello"}\nexit x\n',
 'string_unclosed': 'print("hello)\nexit 0\n',
 'print_value': 'i32 x{print(1)}\nexit x\n',
 'print_empty': 'print()\nexit 0\n',
 'print_many': 'print(1, 2)\nexit 0\n',
 'read_args': 'exit read(1)\n',
 'reserved_var': 'i32 read{1}\nexit 0\n',
 'reserved_fn': 'fn print := () -> i32\n{\n exit 0\n}\nexit 0\n',
 'reserved_param': 'fn f := (i32 read) -> i32\n{\n exit 0\n}\nexit 0\n',
 'reserved_field': 'struct S\n{\n i32 print\n}\nexit 0\n',
 'reserved_method': P.replace('fn d2', 'fn read')+'exit 0\n',
 'reserved_call': P+'Point p{1, 2}\nexit p.print()\n',
 'scalar_chain': P+'Point p{1, 2}\nexit p.d2().x\n',
 'temporary_assign': P+'Point p{1, 2}\np.moved(1).x := 5\nexit 0\n',
 'standalone': P+'Point p{1, 2}\np.d2()\nexit 0\n',
}
ok.update({
 'implicit_mutation': (P.replace('exit add(d2(), d2())', 'exit shift(3)') + 'Point mut p{1, 2}\ni32 n{p.twice()}\nexit p.x\n', 'Program exit with result 4\n', None),
 'name_collision': ('''struct A_b
{
 i32 x
 fn c := () -> i32
 {
  exit x
 }
}
struct A
{
 i32 x
 fn b_c := () -> i32
 {
  exit x
 }
}
fn A_b_c := () -> i32
{
 exit 8
}
A_b a{2}
A b{3}
i32 r{a.c() + b.b_c() + A_b_c()}
exit r
''', 'Program exit with result 13\n', None),
 'lookup': (P + '''fn d2 := () -> i32
{
 exit 99
}
fn fallback := () -> i32
{
 exit 2
}
Point p{3, 4}
i32 r{p.twice() + d2()}
exit r
''', 'Program exit with result 152\n', None),
 'temporary_const_field': (P+C+'Circle c{{3, 4}, 2}\ni32 n{c.grown(1).center.shift(5)}\nexit c.center.x\n', 'Program exit with result 3\n', None),
 'read_factor': ('fn add := (i32 a, i32 b) -> i32\n{\n i32 r{a + b}\n exit r\n}\nexit add(read(), 2)\n', 'Program exit with result 7\n', '5\n'),
 'member_print': (P.replace('x := x + dx', 'print(x)\n  x := x + dx\n  print(x)')+'Point mut p{1, 2}\nexit p.shift(3)\n', '1\n4\nProgram exit with result 4\n', None),
})
err['implicit_mutation_const'] = P.replace('exit add(d2(), d2())', 'exit shift(3)') + 'Point p{1, 2}\nexit p.twice()\n'
err['nested_mutation_const'] = ok['mut_field'][0].replace('Box mut b', 'Box b')
for name, (source, expected, stdin) in ok.items():
 path = Path('tests/ok/p7_' + name)
 path.with_suffix('.txt').write_text(source)
 path.with_suffix('.expected').write_text(expected)
 if stdin is not None: path.with_suffix('.in').write_text(stdin)
 tree = Parser(lex(source.encode())).parse_program()
 SemanticChecker().visit(tree)
 out = io.StringIO()
 with contextlib.redirect_stdout(out): tree.dump()
 path.with_suffix('.ast').write_text(out.getvalue())
for name, source in err.items():
 path = Path('tests/err/p7_' + name)
 path.with_suffix('.txt').write_text(source)
 try:
  tree = Parser(lex(source.encode())).parse_program()
  SemanticChecker().visit(tree)
 except CompileError as e:
  path.with_suffix('.expected').write_text(f'compilation error: {e}\n')
 else: raise AssertionError(name)
