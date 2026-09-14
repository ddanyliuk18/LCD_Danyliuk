; ModuleID = "practice1"
target triple = "x86_64-unknown-linux-gnu"
target datalayout = ""

define i32 @"main"()
{
entry:
  %"a" = alloca i32
  %"b" = alloca i32
  store i32 4, i32* %"a"
  %".3" = load i32, i32* %"a"
  %".4" = mul i32 %".3", 3
  store i32 %".4", i32* %"b"
  %".6" = load i32, i32* %"b"
  %".7" = bitcast [29 x i8]* @"fmt" to i8*
  %".8" = call i32 (i8*, ...) @"printf"(i8* %".7", i32 %".6")
  ret i32 0
}

declare i32 @"printf"(i8* %".1", ...)

@"fmt" = private constant [29 x i8] c"Program exit with result %d\0a\00"