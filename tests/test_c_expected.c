#include <stdio.h>
#define INTL_FLAG 1

// ============================================================
// Group 1: Constant replacement
// ============================================================

void case1_1() {
    doIntl();
}

void case1_2() {
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

void case2_1() { }

void case2_2() { alive(); }

void case2_3() { }

void case2_4() { alive(); }

void case2_5() { alive(); }

// ============================================================
// Group 3: Compound boolean + ternary
// ============================================================

void case3_1() {
}

void case3_2() { int b = false; }

void case3_3() { doSomething(); }

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
    afterCode();
}

void case4_2() {
    doElse();
}

void case4_3() {
    if (someCondition()) {
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
    doA();
    afterCode();
}

void case5_2() {
    doA();
    afterCode();
}

void case5_4() {
    doA();
    afterCode();
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

int case6_1() {
    if (isGranted()) { return 1; }
    return 1;
}

void case6_2() {
    doFirst();
    return;
}

void case6_5() {
    for (int i = 0; i < 10; i++) {
        break;
    }
}

// ============================================================
// Group 7: Single-line if(false)
// ============================================================

int case7_1() {
    return doWork();
}

// ============================================================
// Group 9: Nested
// ============================================================

void case9_1() {
    afterCode();
}

void case9_2() {
    doB();
    afterCode();
}

void case9_4() { foo(4, "intl"); }

void case9_6() { args(context, false, "value"); }

void case9_13() {
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
    } else {
        toEarlyUid();
    }
}

void case11_2() {
    if (type == COSMOS) {
        doComplex();
    } else {
        toSignUp();
    }
}

void case11_4() {
    if (someCondition()) {
        doA();
    }
    afterCode();
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

void case15_1() {
}

void case15_7() {
    doIntl();
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
    return newGPComponent(type);
}

void case19_3() {
    doIntl();
    doCommon();
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

void case20_1() {
    toPwd();
}

void case20_2() {
    doIntl();
}

void case20_5(int x) {
    if (x > 0) {
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
    return;
}

void case17_6() {
    return;
}

void case17_7() {
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
            return buildIntl(type);
        case 2:
            return buildOther(type);
        default:
            return buildDefault(type);
    }
}

int case23_2(int type) {
    switch (type) {
        case 1:
            return 1;
        case 2:
            return 2;
    }
    return -1;
}
