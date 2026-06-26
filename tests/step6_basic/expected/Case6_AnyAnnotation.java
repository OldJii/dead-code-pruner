package com.test;

public class Case6_AnyAnnotation {

    // Case 6.1: 有自定义注解 → 不删
    @Deprecated
    private void deprecatedEmpty() {
    }

    // Case 6.2: 有项目自定义注解 → 不删
    @UnitKey(key = "abc123")
    private boolean annotatedBool() {
        return false;
    }

    // Case 6.3: 多个注解 → 不删
    @SuppressWarnings("unused")
    @Deprecated
    private void multiAnnotation() {
    }

    public void caller() {
        deprecatedEmpty();
        boolean b = annotatedBool();
        multiAnnotation();
    }
}
