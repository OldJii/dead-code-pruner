package com.example;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.io.Serializable;

@JsonIgnoreProperties(ignoreUnknown = true)
public class RuntimePayload implements Serializable {
    private final String serializedValue = "value";
}
