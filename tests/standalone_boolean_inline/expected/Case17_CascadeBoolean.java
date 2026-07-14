package com.test;

// Case 17: standalone 内联后 Phase 1 应进一步简化布尔表达式
class Case17_CascadeBoolean {

    public void test() {
        // standalone inline -> if (false) {...} else {...} -> Phase 1 Step 6 -> 只保留 else 体
        if (false) {
            showLocal();
        } else {
            showPrimary();
        }

        // standalone inline -> false && x -> Phase 1 Step 4 -> false -> Step 6 -> 删除 if 体
        if (false && someCheck()) {
            doLocalStuff();
        }

        // standalone inline -> !false -> Phase 1 Step 3 -> true
        boolean enabled = !false;

        // standalone inline -> false ? a : b -> Phase 1 Step 4 -> b
        String mode = false ? "secondary" : "primary";

        // standalone inline -> false || isReady() -> Phase 1 Step 4 -> isReady()
        boolean ready = false || isReady();

        // standalone inline -> if (!false) -> Phase 1 Step 3 -> if (true) -> Step 6 -> 展开
        if (!false) {
            doModernStuff();
        }
    }
}
