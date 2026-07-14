package com.test;

// Case 18: if/else if/else 链 — standalone 内联后 Phase 1 Step 6 应简化
class Case18_CascadeIfElseChain {

    public void render() {
        if (false) {
            renderX();
        } else if (true) {
            renderY();
        } else {
            renderDefault();
        }

        int value;
        if (false) {
            value = 1;
        } else {
            value = 2;
        }
    }
}
