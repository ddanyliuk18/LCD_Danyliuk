#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
echo '=== Optimized warm-up trees ==='
for name in warmup_chain warmup_shadow; do
 python3 compiler.py --remove-unused --ast-checked "tests/opt/${name}.txt" >actual.ast
 diff -u "tests/opt/${name}.astc" actual.ast
 cat actual.ast
done
echo '=== Three-function chain: result and all defined functions ==='
python3 compiler.py tests/opt/function_chain.txt --remove-unused output.ll
lli output.ll >actual.out
diff -u tests/opt/function_chain.expected actual.out
cat actual.out
grep '^define ' output.ll
test "$(grep -c '^define ' output.ll)" -eq 2
grep -F 'define i32 @"user.twice"' output.ll
echo '=== Bonus: quiet calls removed, loud call preserved ==='
python3 compiler.py --remove-unused --ast-checked tests/opt/bonus_pure.txt >actual.ast
diff -u tests/opt/bonus_pure.astc actual.ast
cat actual.ast
python3 compiler.py --remove-unused tests/opt/bonus_pure.txt output.ll
lli output.ll >actual.out
diff -u tests/opt/bonus_pure.expected actual.out
cat actual.out
echo '=== Runtime, effects, flags and weakref measurement ==='
python3 tools/verify_practice9.py
echo '=== Optimizations note ==='
sed -n '/^## Optimizations/,/^## /p' README.md
if [[ "${1:-}" == --full ]]; then
 bash run_tests.sh
 bash run_tests.sh --remove-unused
else
 echo 'For both complete suite runs: bash tools/demo_practice9.sh --full'
fi
rm -f actual.ast actual.out output.ll
