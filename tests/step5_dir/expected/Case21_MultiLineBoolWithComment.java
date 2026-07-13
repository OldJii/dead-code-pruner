package com.test;

// Case 21: 多行布尔表达式中 && false 前有注释行 — step5 内联后 run_all 应正确处理
class Case21 {

    public void test1() {
        // 场景: 最后一个条件变成 false，应移除该行和注释
        if (!hasChoice()
            && freeRemaining() <= 0
            // Restriction二期优化，不再弹购买弹框
            && !false) {
            showDialog();
            return false;
        }
    }

    public void test2() {
        // 场景: 最后一个条件变成 true，&& true 应消除
        if (hasChoice()
            || freeRemaining() > 0
            // Restriction二期优化
            || false) {
            showFeature();
        }
    }

    public void test3() {
        // 场景: 中间条件变成 false
        if (conditionA()
            && false
            && conditionB()) {
            doWork();
        }
    }
}
