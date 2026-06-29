package com.test;

// Case 20: 全限定名调用 — 应连同包名前缀一起替换
class Case20 {

    public void test() {
        // 简单限定
        boolean a = SomeController.isTest();
        // 全限定名
        boolean b = com.p1.mobile.putong.core.ab.SomeController.isTest();
        // 嵌套包名
        boolean c = com.p1.mobile.putong.core.ab.experiment.OnLineController.isOnline();
        // return 语句中的全限定名
        return com.p1.mobile.putong.core.ab.SomeController.isTest();
    }
}
