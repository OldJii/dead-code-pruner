package com.test;

public class Case9_InnerClass {

    // Case 9.2: 内部类的空方法 → 应删
    private static class InnerHelper {

        public void innerCaller() {
            boolean b = false;
        }
    }

    // Case 9.3: 匿名内部类中的调用不应被错删
    public void caller() {
        InnerHelper h = new InnerHelper();
        h.innerEmpty(); // 这是对象调用，不应被外部类规则删除
    }
}
