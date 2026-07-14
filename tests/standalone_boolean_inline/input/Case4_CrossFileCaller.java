package com.test;

// Case 4: 跨文件调用 public static 方法 — 通过 ClassName.method() 内联
class Case4Caller {

    public void test() {
        if (Case3Controller.isBarLoverExp()) {
            renderLocal();
        }
        boolean flag = Case3Controller.showIntroduction() || isOtherCondition();
        String x = Case3Controller.isBarLoverExp() ? "local" : "intl";
    }
}
