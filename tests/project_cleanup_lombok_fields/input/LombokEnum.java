package com.example;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum LombokEnum {
    FOO("foo", "desc_foo", 1),
    BAR("bar", "desc_bar", 2);

    private final String key;
    private final String desc;
    private final int order;

    public static LombokEnum getByKey(String key) {
        for (LombokEnum e : values()) {
            if (e.key.equals(key)) {
                return e;
            }
        }
        return null;
    }
}
