package com.test;

public class Case2_BooleanConst {

    // Case 2.4: @Override boolean → 不应修改
    @Override
    public boolean isEnabled() {
        return true;
    }

    // Case 2.5: 非常量返回 → 不应修改
    private boolean realLogic() {
        return System.currentTimeMillis() > 0;
    }

    public void caller() {
        // Case 2.7: if 条件中使用
        if (true) {
            System.out.println("always");
        }

        // Case 2.8: if 取反
        if (!false) {
            System.out.println("negated");
        }

        // Case 2.9: 赋值
        boolean b = false;

        // Case 2.10: 保留 @Override 调用
        boolean e = isEnabled();

        // Case 2.11: 保留真实逻辑调用
        boolean r = realLogic();

        // Case 2.12: 静态调用
        boolean s = false;
    }
}
