package com.example;

import lombok.Value;

@Value
public class LombokValueClass {
    String endpoint;
    int timeout;
    boolean secure;
}
