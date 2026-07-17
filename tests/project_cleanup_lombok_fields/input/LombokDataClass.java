package com.example;

import lombok.Data;

@Data
public class LombokDataClass {
    private final String name;
    private final int age;
    private final boolean active;

    public String display() {
        return name + " (" + age + ")";
    }
}
