package com.test;

// Case 12: 多个 private 方法在同一类 — 应分别处理
class Case12 {

    public void test() {
        if (true && !false) {
            doWork();
        }
        boolean a = true;
        boolean b = false;
    }
}
