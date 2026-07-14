package com.test;

public class Case8_MultiLineSignature {

    // Case 8.3: 有实际逻辑 → 不删
    private void withLogic(String a) {
        System.out.println(a);
    }

    public void caller() {
        boolean b = true;
        withLogic("test");
    }
}
