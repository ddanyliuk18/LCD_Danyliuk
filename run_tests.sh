#!/bin/bash

set -u
shopt -s nullglob

passed=0
failed=0

check_ok() {
    input="$1"
    base="${input%.txt}"
    if [[ "$input" == tests/ok/* ]]; then
        expected="${base}.expected"
    else
        expected="${base}.out"
    fi
    expected_ast="${base}.ast"
    rm -f output.ll actual.out actual.err actual.ast

    if ! python3 compiler.py "$input" output.ll >actual.out 2>actual.err; then
        echo "${input} FAIL (compiler rejected it)"
        cat actual.err
        failed=$((failed + 1))
    elif ! python3 compiler.py --ast "$input" >actual.ast 2>actual.err; then
        echo "${input} FAIL (AST mode rejected it)"
        cat actual.err
        failed=$((failed + 1))
    elif ! diff -u "$expected_ast" actual.ast; then
        echo "${input} FAIL (AST differs)"
        failed=$((failed + 1))
    elif ! lli output.ll >actual.out 2>actual.err; then
        echo "${input} FAIL (lli rejected the IR)"
        cat actual.err
        failed=$((failed + 1))
    elif ! diff -u "$expected" actual.out; then
        echo "${input} FAIL (output differs)"
        failed=$((failed + 1))
    else
        echo "${input} PASS"
        passed=$((passed + 1))
    fi
}

check_err() {
    input="$1"
    base="${input%.txt}"
    if [[ "$input" == tests/err/* ]]; then
        expected="${base}.expected"
    else
        expected="${base}.err"
    fi
    rm -f output.ll actual.err

    if python3 compiler.py "$input" output.ll >/dev/null 2>actual.err; then
        echo "${input} FAIL (compiler accepted it)"
        failed=$((failed + 1))
    elif [ -f output.ll ]; then
        echo "${input} FAIL (output.ll exists after an error)"
        failed=$((failed + 1))
    elif ! diff -u "$expected" actual.err; then
        echo "${input} FAIL (diagnostic differs)"
        failed=$((failed + 1))
    else
        echo "${input} PASS"
        passed=$((passed + 1))
    fi
}

echo "=== VALID TESTS ==="
for input in tests/valid*.txt tests/ok/*.txt; do
    check_ok "$input"
done

echo
echo "=== INVALID TESTS ==="
for input in tests/invalid*.txt tests/err/*.txt; do
    check_err "$input"
done

rm -f output.ll actual.out actual.err actual.ast

echo
echo "=== RESULT ==="
echo "Passed: $passed"
echo "Failed: $failed"
test "$failed" -eq 0
