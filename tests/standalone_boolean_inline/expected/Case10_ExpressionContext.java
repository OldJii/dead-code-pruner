package com.test;

// Case 10: 方法调用在各种表达式上下文中 — 应正确替换
class Case10 {

    public void test() {
        int count = true ? 60 : 20;
        String channel = true ? "googleplay" : "local";
        boolean combined = true && hasPermission() || true;
        doAction(true, "param2");
        if (!true) { hide(); }
        boolean neg = !true;
        return true;
    }
}
