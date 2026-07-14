package com.test;

public class Case10_VisibilityEdge {

    private static boolean hadInit = false;

    // Case 10.2: 包访问级别（无修饰符）空方法 → 不应删（不是 private）
    void packageInit() {
    }

    // Case 10.3: protected 空方法 → 不应删
    protected void protectedInit() {
    }

    public void afterField() {
    }

    public void caller() {
        packageInit();
        protectedInit();
        afterField();
    }
}
