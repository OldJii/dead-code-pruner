package com.test;

// Case 22: return 语句前有注释行，&& false 简化不应丢失 return
class Case22 {

    public boolean check() {
        if (condition()) {
            return false;
        }
        // 编辑态、实验组、用户本人
        return isEdit() && isMe() && PayController.isPayWallExp();
    }

    public int getValue() {
        /* 多行注释
           在 return 前面 */
        return PayController.isPayWallExp() ? 10 : 20;
    }
}
