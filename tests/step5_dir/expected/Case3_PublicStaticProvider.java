package com.test;

// Case 3: public static 方法 return false — 应内联调用处，不删除方法定义
class Case3Controller {

    public static boolean isBarLoverExp() {
        return false;
    }

    public static boolean showIntroduction() {
        return false;
    }

    public void localUse() {
        if (false) {
            doSomething();
        }
        if (false) {
            showUI();
        }
    }
}
