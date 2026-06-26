// ============================================================
// Group 1: Constant replacement
// ============================================================

function case1_1() {
    doIntl();
}

function case1_2() {
    afterCode();
}

function case1_3() {
    if (act === fakeLikersAct) {
        showFrom = "intl";
    }
}

function case1_4() {
    // if (INTL_FLAG) { ... }
    /* INTL_FLAG check */
}

function case1_5() {
    const s = "INTL_FLAG is true";
}

function case1_6() { return true; }

function case1_7() { const isIntl = true; doSomething(isIntl); }

function case1_8() { foo(true, "test"); }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

function case2_1() { }

function case2_2() { alive(); }

function case2_3() { }

function case2_4() { alive(); }

function case2_5() { alive(); }

function case2_6() {
    if (notNull(data)) {
        process(data);
    }
}

function case2_7() {
    let b = false;
}

// ============================================================
// Group 3: Compound boolean + ternary
// ============================================================

function case3_1() {
}

function case3_2() { let b = false; }

function case3_3() { doSomething(); }

function case3_4() { let b = true; }

function case3_5() { let val = countDownTimes % (4); }

function case3_6() { let s = "intl"; }

function case3_7() {
}

function case3_8() {
    // if (false && someCondition()) { return; }
}

function case3_9() { forceCalc = forceCalc; }

function case3_10() { if (someCondition()) { doSomething(); } }

function case3_11() { let b = isChinese(); }

function case3_12() { if (someCondition()) { doSomething(); } }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

function case4_1() {
    afterCode();
}

function case4_2() {
    doElse();
}

function case4_3() {
    if (someCondition()) {
        doB();
    } else {
        doC();
    }
    afterCode();
}

function case4_4() {
    if (someCondition()) { doB(); }
    afterCode();
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

function case5_1() {
    doA();
    afterCode();
}

function case5_2() {
    doA();
    afterCode();
}

function case5_4() {
    doA();
    afterCode();
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

function case6_1() {
    if (isGranted()) { return true; }
    return true;
}

function case6_2() {
    doFirst();
    return;
}

function case6_3() {
    throw new Error("error");
}

function case6_5() {
    for (let i = 0; i < 10; i++) {
        break;
    }
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

function case7_1() {
    try { return doWork(); } catch (e) { return 0; }
}

function case7_3() {
    if (url.startsWith("sms:")) { return true; }
    return false;
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

function case9_1() {
    afterCode();
}

function case9_2() {
    doB();
    afterCode();
}

function case9_4() { foo(4, "intl"); }

function case9_6() { args(context, false, "value"); }

function case9_8() { if (checkPermission()) { grant(); } }

function case9_9() {
    doDeep();
    afterCode();
}

function case9_13() {
    alive();
}

// ============================================================
// Group 10: Edge cases
// ============================================================

function case10_1() { let s = "if (true) { do something }"; }

function case10_2() {
    // if (true) {
    //   doSomething();
    // }
    doActual();
}

function case10_4() { a = true; b = false; }

function case10_5() {
    while (true) { if (shouldStop()) break; doWork(); }
}

function case10_7(): boolean { return true; }
function case10_7b(): boolean { return false; }

function case10_9() { setEnabled(true); setVisible(false); }

function case10_12() { let x = arr[0]; }

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

function case12_1() {
    if (notNull(data)) {
        process(data);
    }
}

function case12_2() {
    let ok = check();
}

function case12_3() {
}

function case12_4() {
    let ok = true;
}

// ============================================================
// Group 11: else if (true/false)
// ============================================================

function case11_1() {
    if (signUpType === "cosmos") {
        doComplex();
    } else {
        toEarlyUid();
    }
}

function case11_2() {
    if (signUpType === "cosmos") {
        doComplex();
    } else {
        toSignUp();
    }
}

function case11_3() {
    if (someCondition()) {
        doA();
    } else {
        doB();
    }
}

function case11_4() {
    if (someCondition()) {
        doA();
    }
    afterCode();
}

function case11_5() {
    if (someCondition()) {
        doA();
    } else if (otherCondition()) {
        doB();
    } else {
        doC();
    }
    afterCode();
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

function case13_1() {
    if (equals(nextStage, ethnicitySaved)) {
        doSomething();
    }
}

function case13_3() {
}

function case13_4() {
    if (someCondition()) {
        doSomething();
    }
}

function case13_5() {
    let b = someCondition();
}

// ============================================================
// Group 14: Cross-line ternary
// ============================================================

function case14_1() {
    let cb =
        new MediaLoader(true, false, 200);
}

function case14_2() {
    let label =
        core.recommended;
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

function case15_1() {
}

function case15_7() {
    doIntl();
}

function case16_1() {
    if (local.lock == true
        && remote.lock == false) {
        doSomething();
    }
}

function case16_2() {
    if (flag == false && someCondition()) {
        doSomething();
    }
}

function case16_3() {
    if (someCondition() && flag == true) {
        doSomething();
    }
}

// ============================================================
// Group 17: Dead code after return
// ============================================================

function case17_2() {
    setup();
    return;
}

function case17_5() {
    for (let i = 0; i < 10; i++) {
        continue;
    }
}

function case17_6() {
    return;
}

function case17_7() {
    doSomething();
}

// ============================================================
// Group 18: } boundary
// ============================================================

function case18_1() {
    if (debugBuild && debugFlag) {
        return true;
    }
    return false;
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

function case19_3() {
    doIntl();
    doCommon();
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

function case20_1() {
    toPwd();
}

function case20_2() {
    doIntl();
}

// ============================================================
// Group 22: Nested ternary
// ============================================================

function case22_5(x) {
    return x > 0
            ? R_STRING_A
            : R_STRING_B;
}

function case22_6(x) {
    return R_STRING_C;
}

// ============================================================
// Group 23: Switch/case boundary
// ============================================================

function case23_1(privilege) {
    switch (privilege) {
        case 1:
            return buildIntl(privilege);
        case 2:
            return buildUndo(privilege);
        default:
            return buildDefault(privilege);
    }
}

function case23_2(type) {
    switch (type) {
        case 1:
            return "intl";
        case 2:
            return "other";
    }
}
