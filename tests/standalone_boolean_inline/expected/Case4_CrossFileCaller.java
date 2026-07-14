package com.test;

// Case 4: 跨文件调用 public static 方法 — 通过 ClassName.method() 内联
class Case4Caller {

    public void test() {
        if (false) {
            renderLocal();
        }
        boolean flag = false || isOtherCondition();
        String x = false ? "local" : "intl";
    }
}
