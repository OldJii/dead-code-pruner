package com.example;

public enum PlainEnum {
    A(1),
    B(2);

    private final int code;

    PlainEnum(int code) {
        this.code = code;
    }

    public int getCode() {
        return code;
    }
}
