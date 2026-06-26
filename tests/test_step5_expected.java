package com.test.inline;

import com.other.OtherClass;

// ============================================================
// Case 1: private 方法 return false — 应内联调用 + 删除方法
// ============================================================
class Case1 {

    public void doWork() {
        if (false) {
            System.out.println("local");
        } else {
            System.out.println("intl");
        }
        boolean flag = false && someCondition();
    }
}

// ============================================================
// Case 2: private static 方法 return true — 应内联 + 删除
// ============================================================
class Case2 {

    public void render() {
        if (true) {
            showBanner();
        }
        boolean x = !true;
        String result = true ? "yes" : "no";
    }
}

// ============================================================
// Case 3: public static 方法 return false — 应内联调用（同文件+跨文件），不删除方法
// ============================================================
class Case3Controller {
    public static boolean isBarLoverExp() {
        return false;
    }

    public static boolean showIntroduction() {
        return false;
    }

    public void localUse() {
        if (false) {
            doSomething();
        }
        if (false) {
            showUI();
        }
    }
}

// ============================================================
// Case 4: 跨文件调用 public static 方法 — 应内联 ClassName.method()
// ============================================================
class Case4Caller {
    public void test() {
        if (false) {
            renderLocal();
        }
        boolean flag = false || isOtherCondition();
    }
}

// ============================================================
// Case 5: @Override 方法 — 不应内联，保持不变
// ============================================================
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

// ============================================================
// Case 6: 注释和字符串中的同名方法调用 — 不应被替换
// ============================================================
class Case6 {

    public void test() {
        // if (isDebug()) { ... } 这行不应被修改
        String s = "isDebug() returns false";
        boolean real = false;
        /* false in block comment should not change */
    }
}

// ============================================================
// Case 7: 方法体不是纯 return — 不应被内联
// ============================================================
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
    }
}

// ============================================================
// Case 8: 同名方法在不同类 — 不应误替换
// ============================================================
class Case8A {
    public static boolean isActive() {
        return true;
    }
}

class Case8B {
    public static boolean isActive() {
        return false;
    }

    public void test() {
        // 这里调用的是 Case8A.isActive()，不应被 Case8B 的值替换
        boolean a = Case8A.isActive();
        // 这里调用的是 Case8B.isActive()
        boolean b = Case8B.isActive();
    }
}

// ============================================================
// Case 9: private 方法带参数 — 不应匹配（当前仅处理无参方法）
// ============================================================
class Case9 {

    public void test() {
        if (true) {
            process();
        }
    }
}

// ============================================================
// Case 10: 对象方法调用 obj.method() — 不应被 static 内联替换
// ============================================================
class Case10 {
    public static boolean isReady() {
        return true;
    }

    public void test() {
        Case10 obj = new Case10();
        // obj.isReady() 是实例调用，static 内联应通过 Case10.isReady() 替换
        boolean a = true;
        boolean b = obj.isReady(); // 实例调用也可以内联 static 方法，但风险较高，保守不处理
    }
}

// ============================================================
// Case 11: 方法调用在表达式中间 — 应正确替换
// ============================================================
class Case11 {

    public void test() {
        int count = true ? 60 : 20;
        String channel = true ? "googleplay" : "local";
        boolean combined = true && hasPermission() || true;
        doAction(true, "param2");
    }
}

// ============================================================
// Case 12: Kotlin 风格 — fun 关键字
// ============================================================
class Case12 {

    fun use() {
        if (false) {
            doKotlinThing()
        }
        val enabled = false
    }
}

// ============================================================
// Case 13: 多个 private 方法在同一类 — 应分别处理
// ============================================================
class Case13 {

    public void test() {
        if (true && !false) {
            doWork();
        }
        boolean a = true;
        boolean b = false;
    }
}

// ============================================================
// Case 14: 方法名与局部变量同名 — 不应误替换变量
// ============================================================
class Case14 {

    public void test() {
        boolean isEnabled = checkSomething();
        if (isEnabled) {  // 这是变量，不应替换
            doWork();
        }
        if (true) {  // 这是方法调用，应替换
            doOther();
        }
    }
}

// ============================================================
// Case 15: 注解标记的方法 — 应跳过（可能被反射调用）
// ============================================================
class Case15 {
    @Inject
    private static boolean isInjected() {
        return true;
    }

    @Route(path = "/test")
    public static boolean isRouted() {
        return false;
    }
}

// ============================================================
// Case 16: 方法调用前有换行 — 应正确匹配
// ============================================================
class Case16 {
    public static boolean isMultiLine() {
        return true;
    }

    public void test() {
        boolean result = true;
        if (true) {
            doWork();
        }
    }
}
