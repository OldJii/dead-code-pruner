package com.test;

// Case 7: 方法体不是纯 return — 不应被内联
class Case7 {

    private boolean hasData() {
        if (list == null) return false;
        return true;
    }

    private static boolean isReady() {
        Log.d("TAG", "checking");
        return true;
    }

    public void test() {
        if (hasData()) { process(); }
        if (isReady()) { start(); }
        if (false) { skip(); }
    }
}
