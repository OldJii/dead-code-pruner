package com.test;

public class Case11_ParamMismatch {

    // Case 11.2: 有参非死方法 → 不删（有实际逻辑）
    public View render(Dialog dialog) {
        return new View(dialog);
    }

    // Case 11.4: 有参同名方法（有逻辑）→ 不删
    public void init(String config) {
        System.out.println(config);
    }

    public void caller() {
        // 无参调用 → 应被替换/删除
        boolean r = false;

        // 有参调用 → 不应被修改
        View v = render(someDialog);
        init("config");
    }
}
