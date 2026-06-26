package com.test;

// Case 5: @Override 方法 — 不应处理
class Case5 extends BaseClass {

    @Override
    public boolean isFeatureEnabled() {
        return true;
    }

    public void use() {
        if (isFeatureEnabled()) {
            doFeature();
        }
    }
}
