package com.test;

// Case 8: 带参数的 private 方法 — 不应匹配（仅处理无参方法）
class Case8 {

    public void test() {
        if (true) {
            process();
        }
        if (true) {
            doWork();
        }
    }
}
