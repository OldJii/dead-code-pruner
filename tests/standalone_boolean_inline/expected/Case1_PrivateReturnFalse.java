package com.test;

// Case 1: private 方法 return false — 应内联调用处 + 删除方法定义
class Case1_PrivateReturnFalse {

    public void doWork() {
        if (false) {
            System.out.println("local");
        } else {
            System.out.println("intl");
        }
        boolean flag = false && someCondition();
        String result = false ? "a" : "b";
    }
}
