#!/bin/bash

set -u

passed=0
failed=0

echo "=== VALID TESTS ==="

for input in tests/valid*.txt; do
    base="${input%.txt}"
    expected="${base}.out"

    rm -f output.ll

    if python3 compiler.py "$input" output.ll >/dev/null 2>actual.err; then
        actual=$(lli output.ll)
        expected_text=$(cat "$expected")

        if [ "$actual" = "$expected_text" ]; then
            echo "$(basename "$input") PASS"
            passed=$((passed + 1))
        else
            echo "$(basename "$input") FAIL"
            echo "  expected: $expected_text"
            echo "  actual:   $actual"
            failed=$((failed + 1))
        fi
    else
        echo "$(basename "$input") FAIL"
        echo "  compiler unexpectedly returned an error:"
        cat actual.err
        failed=$((failed + 1))
    fi
done


echo
echo "=== INVALID TESTS ==="

for input in tests/invalid*.txt; do
    base="${input%.txt}"
    expected="${base}.err"

    rm -f output.ll actual.err

    python3 compiler.py "$input" output.ll >/dev/null 2>actual.err
    status=$?

    if [ "$status" -eq 0 ]; then
        echo "$(basename "$input") FAIL"
        echo "  compiler accepted invalid program"
        failed=$((failed + 1))
        continue
    fi

    if [ -f output.ll ]; then
        echo "$(basename "$input") FAIL"
        echo "  output.ll exists after compilation error"
        failed=$((failed + 1))
        continue
    fi

    if diff -q "$expected" actual.err >/dev/null; then
        echo "$(basename "$input") PASS"
        passed=$((passed + 1))
    else
        echo "$(basename "$input") FAIL"
        echo "  expected:"
        cat "$expected"
        echo "  actual:"
        cat actual.err
        failed=$((failed + 1))
    fi
done


rm -f output.ll actual.err

echo
echo "=== RESULT ==="
echo "Passed: $passed"
echo "Failed: $failed"

if [ "$failed" -eq 0 ]; then
    exit 0
else
    exit 1
fi
