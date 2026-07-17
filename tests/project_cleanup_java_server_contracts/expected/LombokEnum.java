package com.example;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum LombokEnum {
    FIRST("one", "first", "[1] "),
    SECOND("two", "second", "[2] ");

    private final String code;
    private final String description;
    private final String titlePrefix;
}
