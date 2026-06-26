package com.test;

// Case 6: 注释和字符串中的同名方法调用 — 不应被替换
class Case6 {

    public void test() {
        // if (isDebug()) { ... } 这行不应被修改
        String s = "isDebug() returns false";
        boolean real = false;
        /* isDebug() in block comment should not change */
    }
}
