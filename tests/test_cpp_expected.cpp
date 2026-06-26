// C++ test cases for dead-code-pruner
#define INTL_FLAG 1

// ============================================================
// Group 1: Constant replacement
// ============================================================

void case1_1() {
    if (true) { doIntl(); }
}

void case1_2() {
    if (false) { doDomestic(); }
    afterCode();
}

void case1_3() {
    if (act == fakeLikersAct) {
        showFrom = "intl";
    }
}

void case1_4() {
    // if (INTL_FLAG) { ... }
    /* INTL_FLAG check */
}

void case1_5() {
    char *s = "INTL_FLAG is true";
}

int case1_6() { return true; }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

void case2_1() { if (false) { dead(); } }

void case2_2() { if (true) { alive(); } }

void case2_3() { if (false) { dead(); } }

void case2_4() { if (true) { alive(); } }

void case2_5() { if (true) { alive(); } }

// ============================================================
// Group 3: Compound boolean + ternary
// ============================================================

void case3_1() {
    if (false) { doSomething(); }
}

void case3_2() { int b = false; }

void case3_3() { if (true) { doSomething(); } }

void case3_4() { int b = true; }

void case3_5() { int val = countDownTimes % (4); }

void case3_6() { char *s = "intl"; }

void case3_9() { forceCalc = forceCalc; }

void case3_10() { if (someCondition()) { doSomething(); } }

void case3_11() { int b = isChinese(); }

void case3_12() { if (someCondition()) { doSomething(); } }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

void case4_1() {
    if (false) { deadCode(); }
    afterCode();
}

void case4_2() {
    if (false) { deadCode(); } else { doElse(); }
}

void case4_3() {
    if (false) {
        deadCode();
    } else if (someCondition()) {
        doB();
    } else {
        doC();
    }
    afterCode();
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

void case5_1() {
    if (true) { doA(); }
    afterCode();
}

void case5_2() {
    if (true) { doA(); } else { doB(); }
    afterCode();
}

void case5_4() {
    if (true) {
        doA();
    } else if (someCondition()) {
        doB();
    } else {
        doC();
    }
    afterCode();
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

int case6_1() {
    if (isGranted()) { return 1; }
    if (true) { return 1; }
    return isAllGranted();
}

void case6_2() {
    doFirst();
    if (true) { return; }
    doSecond();
    doThird();
}

void case6_5() {
    for (int i = 0; i < 10; i++) {
        if (true) { break; }
        processItem(i);
    }
}

// ============================================================
// Group 7: Single-line if(false)
// ============================================================

int case7_1() {
    if (false) return -1;
    return doWork();
}

// ============================================================
// Group 9: Nested
// ============================================================

void case9_1() {
    if (false) { if (true) { doA(); } doB(); }
    afterCode();
}

void case9_2() {
    if (false) { doA(); }
    if (true) { doB(); }
    afterCode();
}

void case9_4() { foo(4, "intl"); }

void case9_6() { args(context, false, "value"); }

void case9_13() {
    if (false) { dead1(); }
    if (false) { dead2(); }
    alive();
}

// ============================================================
// Group 10: Edge cases
// ============================================================

void case10_1() { char *s = "if (true) { do something }"; }

void case10_4() { a = true; b = false; }

void case10_5() {
    while (true) { if (shouldStop()) break; doWork(); }
}

int case10_7() { return true; }
int case10_7b() { return false; }

void case10_9() { setEnabled(true); setVisible(false); }

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

void case12_1() {
    if (notNull(data)) {
        process(data);
    }
}

void case12_2() {
    int ok = check();
}

void case12_3() {
    if (false) {
        dead();
    }
}

void case12_4() {
    int ok = true;
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

void case13_1() {
    if (someCondition()) {
        doSomething();
    }
}

void case13_3() {
    if (false) {
        doSomething();
    }
}

void case13_4() {
    if (someCondition()) {
        doSomething();
    }
}

// ============================================================
// Group 14: Cross-line ternary
// ============================================================

void case14_1() {
    int cb =
        createCallbackA();
}

void case14_2() {
    char *label =
        "recommended";
}

// ============================================================
// Group 11: else if (true/false)
// ============================================================

void case11_1() {
    if (type == COSMOS) {
        doComplex();
    } else if (true) {
        toEarlyUid();
    } else {
        toSignUp();
    }
}

void case11_2() {
    if (type == COSMOS) {
        doComplex();
    } else if (false) {
        doDead();
    } else {
        toSignUp();
    }
}

void case11_4() {
    if (someCondition()) {
        doA();
    } else if (false) {
        doDead();
    }
    afterCode();
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

void case15_1() {
    if (false) {
        doSomething();
    }
}

void case15_7() {
    if (true) {
        doIntl();
    }
}

void case16_1() {
    if (local.lock == true && remote.lock == false) {
        doSomething();
    }
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

void* case19_1(int type) {
    if (true) {
        return newGPComponent(type);
    } else if (type == 1) {
        return newLocalComponent(type);
    }
    return newDefaultComponent(type);
}

void case19_3() {
    if (true) {
        doIntl();
    } else {
        doLocal();
    }
    doCommon();
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

void case20_1() {
    if (true) toPwd();
    else loginStrategy();
}

void case20_2() {
    if (false) doLocal();
    else doIntl();
}

void case20_5(int x) {
    if (false) doLocal();
    else if (x > 0) {
        doPositive();
    } else {
        doNegative();
    }
}

// ============================================================
// Group 17: Dead code after return
// ============================================================

void case17_2() {
    setup();
    if (true) return;
    doSomethingA();
    doSomethingB();
}

void case17_6() {
    if (true) return;
}

void case17_7() {
    if (false) return;
    doSomething();
}

// ============================================================
// Group 18: } boundary
// ============================================================

int case18_1() {
    if (debugBuild && debugFlag) {
        return 1;
    }
    return false;
}

void case18_4() {
    for (int i = 0; i < 10; i++) {
        process(i);
    }
    int result = false;
}

// ============================================================
// Group 22: Nested ternary
// ============================================================

int case22_5(int x) {
    return x > 0
            ? R_STRING_A
            : R_STRING_B;
}

int case22_6(int x) {
    return R_STRING_C;
}

// ============================================================
// Group 23: Switch/case boundary
// ============================================================

int case23_1(int type) {
    switch (type) {
        case 1:
            if (true) {
                return buildIntl(type);
            }
            return buildLocal(type);
        case 2:
            return buildOther(type);
        default:
            return buildDefault(type);
    }
}

int case23_2(int type) {
    switch (type) {
        case 1:
            if (true) {
                return 1;
            } else {
                return 0;
            }
        case 2:
            return 2;
    }
    return -1;
}
