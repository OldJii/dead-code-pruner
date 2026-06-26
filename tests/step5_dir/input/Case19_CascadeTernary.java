package com.test;

// Case 19: 三元表达式级联简化
class Case19_CascadeTernary {

    public void test() {
        // step5 -> false ? 10 : 20  -> step3 -> 20
        int timeout = false ? 10 : 20;

        // step5 -> false ? "old" : "new"  -> step3 -> "new"
        String label = false ? "old" : "new";

        // 嵌套三元
        String result = false ? (isValid() ? "a" : "b") : "c";
    }
}
