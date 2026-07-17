package com.example;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class LombokBuilderClass {
    private final String host;
    private final int port;
    private final boolean ssl;
}
