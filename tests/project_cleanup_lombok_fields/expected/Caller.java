package com.example;

public class Caller {
    public void run() {
        LombokEnum e = LombokEnum.getByKey("foo");
        LombokDataClass d = new LombokDataClass("test", 1, true);
        String s = d.display();
        PlainEnum p = PlainEnum.A;
        int code = p.getCode();
    }
}
