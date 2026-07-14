package com.test;

/**
 * 测试跳过规则
 */
public class Case7_SkipPatterns {

    // Case 7.1: __find_views_ 命名 → 跳过
    private void __find_views_fragment() {
    }

    // Case 7.2: 构造函数不应被匹配
    // (构造函数没有返回类型，不会匹配 void/boolean 模式)

    // Case 7.3: 接口方法（这里不适用，Java接口方法没有方法体）

    public void caller() {
        __find_views_fragment();
        boolean f = false;
        boolean f2 = false;
    }
}
