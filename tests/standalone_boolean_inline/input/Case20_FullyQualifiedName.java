package com.test;

// Case 20: 全限定名调用 — 应连同包名前缀一起替换
class Case20 {

    public void test() {
        // 简单限定
        boolean a = PrimaryFlagController.isTest();
        // 全限定名
        boolean b = org.example.flags.PrimaryFlagController.isTest();
        // 嵌套包名
        boolean c = org.example.flags.experiment.SecondaryFlagController.isOnline();
        // return 语句中的全限定名
        return org.example.flags.PrimaryFlagController.isTest();
    }
}
