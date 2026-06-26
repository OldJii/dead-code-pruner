package com.test;

// Case 13: 方法名与局部变量同名 — 不应误替换变量
class Case13 {

    public void test() {
        boolean isEnabled = checkSomething();
        if (isEnabled) {
            doWork();
        }
        if (true) {
            doOther();
        }
        boolean result = true && isEnabled;
    }
}
