"""Create source fixtures; runtime results are independently specified below."""
from pathlib import Path

POINT = 'struct Point\n{\n i32 mut x\n i32 mut y\n}\n'
CIRCLE = POINT + 'struct Circle\n{\n Point center\n i32 mut radius\n}\n'
ALL_MUT = POINT + 'struct Box\n{\n Point mut p\n}\n'
ok = {
 'p6_nested_chain': (CIRCLE + 'Point p{10, 20}\nCircle c{p, 5}\nexit c.center.x\n', '10'),
 'p6_field_write': (ALL_MUT + 'Point p{1, 2}\nBox mut b{p}\nb.p.x := 9\nexit b.p.x\n', '9'),
 'p6_struct_parameter': (POINT + 'fn get := (Point p) -> i32\n{\n exit p.y\n}\nPoint p{3, 7}\nexit get(p)\n', '7'),
 'p6_struct_result': (POINT + 'fn make := () -> Point\n{\n Point p{3, 4}\n exit p\n}\nPoint p{make()}\nexit p.x\n', '3'),
 'p6_nested_calls': ('fn add := (i32 a, i32 b) -> i32\n{\n i32 x{a + b}\n exit x\n}\nexit add(10, add(2, 3))\n', '15'),
 'p6_widen_argument': ('fn wide := (i64 x) -> i64\n{\n exit x\n}\ni32 x{7}\nexit wide(x)\n', '7'),
 'p6_task2': ('fn check := (i32 x, bool flag) -> bool\n{\n i32 mut y{3}\n if flag\n {\n  y := y + x\n }\n bool result{y == 10}\n exit result\n}\nbool a{check(7, true)}\nexit a\n', 'true'),
 'p6_fib': ('fn fib := (i32 n) -> i32\n{\n if n == 0\n {\n  exit 0\n }\n if n == 1\n {\n  exit 1\n }\n i32 result{fib(n - 1) + fib(n - 2)}\n exit result\n}\nexit fib(10)\n', '55'),
 'p6_task3': (CIRCLE + 'fn add := (i32 a, i32 b) -> i32\n{\n i32 sum{a + b}\n exit sum\n}\nfn isXZero := (Point p) -> bool\n{\n bool zero{p.x == 0}\n exit zero\n}\nfn moved := (Point p, i32 dx) -> Point\n{\n Point q{p.x + dx, p.y}\n exit q\n}\nPoint p{10, 20}\nCircle c{p, 5}\ni32 xCoord{c.center.x}\nbool z{isXZero(p)}\nPoint mut r{moved(p, 1)}\nr := moved(r, 2)\ni32 result{add(xCoord, add(r.x, c.radius))}\nexit result\n', '28'),
 'p6_additional': (POINT + 'struct Circle\n{\n Point center\n i64 mut radius\n}\nstruct Ring\n{\n Circle outer\n Circle inner\n}\ni32 r{5}\nRing g{{{10, 20}, r}, {{10, 20}, 2}}\nCircle c{{1, 2}, g.outer.radius * 3}\ni64 result{c.radius + g.inner.center.y + c.center.x}\nexit result\n', '36'),
 'p6_forward_runtime_names': ('fn main := () -> i32\n{\n exit printf()\n}\nfn printf := () -> i32\n{\n exit 8\n}\nexit main()\n', '8'),
 'p6_copy': (POINT + 'Point mut p{1, 2}\nPoint q{p}\np.x := 5\nexit q.x\n', '1'),
 'p6_all_mut_replace': (ALL_MUT + 'Point p{1, 2}\nPoint q{7, 8}\nBox mut b{p}\nBox c{q}\nb := c\nexit b.p.y\n', '8'),
 'p6_mutual': ('fn even := (i32 n) -> bool\n{\n if n == 0\n {\n  exit true\n }\n exit odd(n - 1)\n}\nfn odd := (i32 n) -> bool\n{\n if n == 0\n {\n  exit false\n }\n exit even(n - 1)\n}\nexit even(8)\n', 'true'),
 'p6_bool_field': ('struct Flag\n{\n bool mut set\n}\nFlag mut f{false}\nf.set := !f.set\nexit f.set\n', 'true'),
 'p6_function_loop': ('fn sum := (i32 n) -> i32\n{\n i32 mut i{0}\n i32 mut s{0}\n while i != n\n {\n  i := i + 1\n  s := s + i\n }\n exit s\n}\nexit sum(10)\n', '55'),
}
err = {
 'unknown_field': POINT + 'Point p{1, 2}\nexit p.z\n',
 'value_count': POINT + 'Point p{1, 2, 3}\nexit 0\n',
 'const_link': CIRCLE + 'Point p{1, 2}\nCircle mut c{p, 3}\nc.center.x := 8\nexit 0\n',
 'argument_count': 'fn f := (i32 x) -> i32\n{\n exit x\n}\nexit f()\n',
 'return_type': 'fn f := () -> bool\n{\n exit 1\n}\nexit 0\n',
 'function_order': 'i32 x{0}\nfn f := () -> i32\n{\n exit 0\n}\nexit x\n',
 'nested_builtin': POINT + 'Point p{{1, 2}, 3}\nexit 0\n',
 'nested_count': CIRCLE + 'Circle c{{1}, 3}\nexit 0\n',
 'const_object': POINT + 'Point p{1, 2}\np.x := 3\nexit 0\n',
 'const_whole': CIRCLE + 'Point p{1, 2}\nCircle mut c{p, 3}\nCircle d{p, 4}\nc := d\nexit 0\n',
 'unknown_function': 'exit missing()\n',
 'argument_type': 'fn f := (bool x) -> bool\n{\n exit x\n}\nexit f(1)\n',
 'narrow_call': 'fn f := () -> i64\n{\n exit 2147483648\n}\ni32 x{f()}\nexit x\n',
 'parameter_write': 'fn f := (i32 x) -> i32\n{\n x := 1\n exit x\n}\nexit f(0)\n',
 'global_visibility': 'fn f := () -> i32\n{\n exit x\n}\ni32 x{5}\nexit f()\n',
 'self_struct': 'struct Self\n{\n Self x\n}\nexit 0\n',
 'forward_struct': 'struct A\n{\n B x\n}\nstruct B\n{\n i32 x\n}\nexit 0\n',
 'empty_struct': 'struct A\n{\n}\nexit 0\n',
 'duplicate_field': 'struct A\n{\n i32 x\n bool x\n}\nexit 0\n',
 'duplicate_function': 'fn f := () -> i32\n{\n exit 0\n}\nfn f := () -> i32\n{\n exit 0\n}\nexit 0\n',
 'duplicate_parameter': 'fn f := (i32 x, i32 x) -> i32\n{\n exit x\n}\nexit 0\n',
 'missing_return': 'fn f := () -> i32\n{\n i32 x{0}\n}\nexit 0\n',
 'nested_function': 'fn f := () -> i32\n{\n fn g := () -> i32\n {\n  exit 0\n }\n exit 0\n}\nexit 0\n',
 'struct_order': 'fn f := () -> i32\n{\n exit 0\n}\nstruct A\n{\n i32 x\n}\nexit 0\n',
 'struct_exit': POINT + 'Point p{1, 2}\nexit p\n',
 'call_statement': 'fn f := () -> i32\n{\n exit 0\n}\nf()\nexit 0\n',
 'grouping': 'i32 x{(1 + 2)}\nexit x\n',
 'unary_minus': 'i32 x{-1}\nexit x\n',
 'exit_operation': 'exit 1 + 2\n',
 'parameter_field_write': POINT + 'fn f := (Point p) -> i32\n{\n p.x := 4\n exit p.x\n}\nexit 0\n',
}
for name, (source, result) in ok.items():
    base = Path('tests/ok') / name
    base.with_suffix('.txt').write_text(source)
    base.with_suffix('.expected').write_text(f'Program exit with result {result}\n')
for name, source in err.items():
    (Path('tests/err') / ('p6_' + name + '.txt')).write_text(source)
