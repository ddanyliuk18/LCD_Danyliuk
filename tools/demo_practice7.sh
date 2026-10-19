#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
python3 compiler.py --ast tests/ok/p7_task1.txt
python3 compiler.py tests/ok/p7_task1.txt output.ll
lli output.ll
sed -n '/define i32 @"Point_shift"/,/^}/p' output.ll
for name in field_after const_object; do
 if python3 compiler.py "tests/err/p7_${name}.txt" rejected.ll; then
  echo "Expected rejection" >&2
  exit 1
 fi
done
python3 compiler.py tests/ok/p7_task3.txt output.ll
lli output.ll < tests/ok/p7_task3.in
python3 compiler.py tests/ok/p7_bonus.txt additional.ll
lli additional.ll
