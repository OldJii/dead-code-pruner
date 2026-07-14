package com.test;

// Case 9: 带注解的方法 — 应跳过（可能被反射调用）
class Case9 {

    @Inject
    private static boolean isInjected() {
        return true;
    }

    @Route(path = "/test")
    public static boolean isRouted() {
        return false;
    }

    public void test() {
        if (isInjected()) { a(); }
        if (true) { b(); }
    }
}
