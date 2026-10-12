#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for case in p6_task2 p6_fib p6_task3 p6_additional; do
    python3 compiler.py "tests/ok/$case.txt" output.ll
    lli output.ll
done
python3 compiler.py tests/ok/p6_task3.txt output.ll
grep -E 'Point.*type|getelementptr|define .*user\.|call .*user\.' output.ll
for case in unknown_field const_link return_type; do
    if python3 compiler.py "tests/err/p6_$case.txt" rejected.ll; then
        echo "Unexpected acceptance: $case" >&2
        exit 1
    fi
    test ! -e rejected.ll
done
