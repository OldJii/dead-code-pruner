package com.test;

// Case 19: 三元表达式级联简化
class Case19_CascadeTernary {

    public void test() {
        // standalone inline -> false ? 10 : 20 -> Phase 1 Step 4 -> 20
        int timeout = false ? 10 : 20;

        // standalone inline -> false ? "old" : "new" -> Phase 1 Step 4 -> "new"
        String label = false ? "old" : "new";

        // 嵌套三元
        String result = false ? (isValid() ? "a" : "b") : "c";
    }
}
