package com.test;

public class Case5_SameNameDiffClass {

    // Case 5.3: 调用另一个类的 init() → 不应被删（它不是死方法）
    public void setupOther(OtherClass other) {
        other.init();
    }

    // Case 5.4: 静态调用另一个类 → 不应被删
    public void callStatic() {
        OtherClass.staticInit();
    }

    // Case 5.7: 使用另一个类的 check() → 不应被替换
    public boolean checkOther(OtherClass other) {
        return other.check();
    }
}

class OtherClass {
    // 这个 init() 不是空方法
    public void init() {
        System.out.println("real init");
    }

    public static void staticInit() {
        System.out.println("static init");
    }

    public boolean check() {
        return true;
    }
}
