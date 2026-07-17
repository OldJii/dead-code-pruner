package com.example;

public enum PlainEnum {
    A(1),
    B(2);

    private final int code;
    private static final String UNUSED_CONST = "should_be_removed";

    PlainEnum(int code) {
        this.code = code;
    }

    public int getCode() {
        return code;
    }
}
