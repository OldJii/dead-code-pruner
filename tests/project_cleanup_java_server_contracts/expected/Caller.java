package com.example;

public class Caller {
    public String render(LombokEnum value, GetterDto dto) {
        return value.getTitlePrefix() + dto.getExternal();
    }
}
