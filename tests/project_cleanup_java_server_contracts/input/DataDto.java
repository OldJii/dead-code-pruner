package com.example;

import lombok.Data;

@Data
public class DataDto {
    private final String id;
    private String displayName;
    private static final String UNUSED_DATA_KEY = "unused";
}
