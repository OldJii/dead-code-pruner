package com.test;

// Case 2: private static 方法 return true — 应内联 + 删除
class Case2_PrivateStaticReturnTrue {

    public void render() {
        if (true) {
            showBanner();
        }
        boolean x = !true;
        String result = true ? "yes" : "no";
    }
}
