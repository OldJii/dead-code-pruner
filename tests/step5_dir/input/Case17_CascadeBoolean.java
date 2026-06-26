package com.test;

// Case 17: step5 内联后 run_all 应进一步简化布尔表达式
class Case17_CascadeBoolean {

    public void test() {
        // step5 -> if (false) {...} else {...}  -> step4 -> 只保留 else 体
        if (false) {
            showLocal();
        } else {
            showIntl();
        }

        // step5 -> false && x  -> step3 -> false  -> step4 -> 删除 if 体
        if (false && someCheck()) {
            doLocalStuff();
        }

        // step5 -> !false  -> step2 -> true
        boolean enabled = !false;

        // step5 -> false ? a : b  -> step3 -> b
        String mode = false ? "local" : "intl";

        // step5 -> false || isReady()  -> step3 -> isReady()
        boolean ready = false || isReady();

        // step5 -> if (!false)  -> step2 -> if (true)  -> step4 -> 展开
        if (!false) {
            doModernStuff();
        }
    }
}
