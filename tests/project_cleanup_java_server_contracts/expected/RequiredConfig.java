package com.example;

import lombok.RequiredArgsConstructor;

@RequiredArgsConstructor
public class RequiredConfig {
    private final String required;
    private static final String RUNTIME_VALUE = loadRuntimeValue();

    private static String loadRuntimeValue() {
        return System.getProperty("runtime.value");
    }
}
