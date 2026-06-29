package com.test;

// Case 14: 实例方法调用 obj.method() — static 内联不应替换实例调用
class Case14 {

    public static boolean isReady() {
        return true;
    }

    public void test() {
        Case14 obj = new Case14();
        boolean a = true;
        boolean b = obj.isReady();
        boolean c = getHelper().isReady();
    }
}
