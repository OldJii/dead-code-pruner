package com.test;

public class Case1_VoidEmpty {

    // Case 1.4: @Override 空方法 → 不应删除
    @Override
    protected void onDestroy() {
    }

    // Case 1.5: public 空方法 → 应跨文件搜索再决定；这里假设无引用 → 删除
    public void unusedPublicEmpty() {
    }

    // Case 1.7: 非空方法 → 不应删除
    private void realMethod() {
        System.out.println("hello");
    }

    public void caller() {
        onDestroy();
        realMethod();

        // Case 1.9: 调用在 if 中
        if (true) {
        }

        // Case 1.10: 调用是语句的一部分（链式调用等）
        String s = "test";
        s.toString(); // 不相关，不应被删
    }
}
