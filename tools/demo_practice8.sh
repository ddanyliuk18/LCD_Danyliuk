#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
for name in task1 task2 bonus; do
 echo "=== Practice 8: $name ==="
 python3 compiler.py "tests/ok/p8_${name}.txt" output.ll
 lli output.ll >actual.out
 diff -u "tests/ok/p8_${name}.expected" actual.out
 cat actual.out
 if [[ "$name" == task2 ]]; then
  python3 compiler.py --ast-checked tests/ok/p8_task2.txt
  grep -F '%"lambda.add_k" = type {i32}' output.ll
  sed -n '/define i32 @"lambda.add_k_call"/,/^}/p' output.ll
 fi
done
for name in missing argument const_nested; do
 echo "=== Expected rejection: $name ==="
 if python3 compiler.py "tests/err/p8_${name}.txt" rejected.ll 2>actual.err; then
  echo 'Expected rejection' >&2
  exit 1
 fi
 test ! -e rejected.ll
 diff -u "tests/err/p8_${name}.expected" actual.err
 cat actual.err
done
rm -f actual.out actual.err output.ll
