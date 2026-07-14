package com.test;

// Case 15: 方法调用跨行 — 应正确匹配
class Case15 {

    public static boolean isMultiLine() {
        return true;
    }

    public void test() {
        boolean result = Case15
            .isMultiLine();
        if (Case15.
            isMultiLine()) {
            doWork();
        }
        boolean simple = Case15.isMultiLine();
    }
}
