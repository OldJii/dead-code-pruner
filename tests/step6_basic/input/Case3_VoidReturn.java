package com.test;

public class Case3_VoidReturn {

    // Case 3.6: @Inject 注解方法 → 不删
    @javax.inject.Inject
    private void injectedMethod() {
    }

    public void caller() {
        injectedMethod();

        String x = "hello";

        // Case 3.4 测试
        if (x.length() > 0) {
        }

        // Case 3.5 测试
        System.out.println("after mixed");
    }
}
