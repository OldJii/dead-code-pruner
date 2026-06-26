// ============================================================
// Group 1: Constant replacement
// ============================================================

function case1_1() {
    if (INTL_FLAG) { doIntl(); }
}

function case1_2() {
    if (!INTL_FLAG) { doDomestic(); }
    afterCode();
}

function case1_3() {
    if (INTL_FLAG && act === fakeLikersAct) {
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

function case1_6() { return INTL_FLAG; }

function case1_7() { const isIntl = INTL_FLAG; doSomething(isIntl); }

function case1_8() { foo(INTL_FLAG, "test"); }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

function case2_1() { if (!true) { dead(); } }

function case2_2() { if (!false) { alive(); } }

function case2_3() { if (true == false) { dead(); } }

function case2_4() { if (true != false) { alive(); } }

function case2_5() { if (false == false) { alive(); } }

function case2_6() {
    if (notNull(data) && (true)) {
        process(data);
    }
}

function case2_7() {
    let b = isSomething() && (false);
}

// ============================================================
// Group 3: Compound boolean + ternary
// ============================================================

function case3_1() {
    if (false && data.picksGuideUser) { doSomething(); }
}

function case3_2() { let b = isChinese() && false; }

function case3_3() { if (true || someCondition()) { doSomething(); } }

function case3_4() { let b = someCondition() || true; }

function case3_5() { let val = countDownTimes % (false ? 2 : 4); }

function case3_6() { let s = true ? "intl" : "local"; }

function case3_7() {
    if (false && !isEmpty(identifier) && identifier.includes("guideNewUser")) {
        doSomething();
    }
}

function case3_8() {
    // if (false && someCondition()) { return; }
}

function case3_9() { forceCalc = forceCalc || false; }

function case3_10() { if (true && someCondition()) { doSomething(); } }

function case3_11() { let b = isChinese() && true; }

function case3_12() { if (false || someCondition()) { doSomething(); } }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

function case4_1() {
    if (false) { deadCode(); }
    afterCode();
}

function case4_2() {
    if (false) { deadCode(); } else { doElse(); }
}

function case4_3() {
    if (false) {
        deadCode();
    } else if (someCondition()) {
        doB();
    } else {
        doC();
    }
    afterCode();
}

function case4_4() {
    if (false) { deadCode(); } else if (someCondition()) { doB(); }
    afterCode();
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

function case5_1() {
    if (true) { doA(); }
    afterCode();
}

function case5_2() {
    if (true) { doA(); } else { doB(); }
    afterCode();
}

function case5_4() {
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

function case6_1() {
    if (isGranted()) { return true; }
    if (true) { return true; }
    return isAllGranted();
}

function case6_2() {
    doFirst();
    if (true) { return; }
    doSecond();
    doThird();
}

function case6_3() {
    if (true) { throw new Error("error"); }
    cleanup();
}

function case6_5() {
    for (let i = 0; i < 10; i++) {
        if (true) { break; }
        processItem(i);
    }
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

function case7_1() {
    if (false) return -1;
    try { return doWork(); } catch (e) { return 0; }
}

function case7_3() {
    if (false) return false;
    if (url.startsWith("sms:")) { return true; }
    return false;
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

function case9_1() {
    if (false) { if (true) { doA(); } doB(); }
    afterCode();
}

function case9_2() {
    if (false) { doA(); }
    if (true) { doB(); }
    afterCode();
}

function case9_4() { foo(false ? 2 : 4, true ? "intl" : "local"); }

function case9_6() { args(context, !true, "value"); }

function case9_8() { if (true && checkPermission()) { grant(); } }

function case9_9() {
    if (true) { if (true) { doDeep(); } }
    afterCode();
}

function case9_13() {
    if (false) { dead1(); }
    if (false) { dead2(); }
    if (false) { dead3(); }
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

function case10_4() { a = !false; b = !true; }

function case10_5() {
    while (true) { if (shouldStop()) break; doWork(); }
}

function case10_7() { return true; }
function case10_7b() { return false; }

function case10_9() { setEnabled(true); setVisible(false); }

function case10_12() { let x = arr[true ? 0 : 1]; }

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

function case12_1() {
    if (notNull(data) && (true)) {
        process(data);
    }
}

function case12_2() {
    let ok = check() || (false);
}

function case12_3() {
    if ((false) && someCheck()) {
        dead();
    }
}

function case12_4() {
    let ok = (true) || someCondition();
}

// ============================================================
// Group 11: else if (true/false)
// ============================================================

function case11_1() {
    if (signUpType === "cosmos") {
        doComplex();
    } else if (true) {
        toEarlyUid();
    } else {
        toSignUp();
    }
}

function case11_2() {
    if (signUpType === "cosmos") {
        doComplex();
    } else if (false) {
        doDead();
    } else {
        toSignUp();
    }
}

function case11_3() {
    if (someCondition()) {
        doA();
    } else if (true) {
        doB();
    }
}

function case11_4() {
    if (someCondition()) {
        doA();
    } else if (false) {
        doDead();
    }
    afterCode();
}

function case11_5() {
    if (someCondition()) {
        doA();
    } else if (false) {
        doDead();
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
    if (true
        && equals(nextStage, ethnicitySaved)) {
        doSomething();
    }
}

function case13_3() {
    if (false
        && someCondition()
        && anotherCondition()) {
        doSomething();
    }
}

function case13_4() {
    if (someCondition() &&
        true) {
        doSomething();
    }
}

function case13_5() {
    let b = someCondition()
        || false;
}

// ============================================================
// Group 14: Cross-line ternary
// ============================================================

function case14_1() {
    let cb =
        true
            ? new MediaLoader(true, false, 200)
            : new MediaLoader(true, false, 100);
}

function case14_2() {
    let label =
        false
            ? core.suggested
            : core.recommended;
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

function case15_1() {
    if (position === 0 && !INTL_FLAG) {
        doSomething();
    }
}

function case15_7() {
    if (position === 0 || INTL_FLAG) {
        doIntl();
    }
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
    if (INTL_FLAG) return;
    doSomethingA();
    doSomethingB();
}

function case17_5() {
    for (let i = 0; i < 10; i++) {
        if (INTL_FLAG) continue;
        doSomething(i);
    }
}

function case17_6() {
    if (INTL_FLAG) return;
}

function case17_7() {
    if (!INTL_FLAG) return;
    doSomething();
}

// ============================================================
// Group 18: } boundary
// ============================================================

function case18_1() {
    if (debugBuild && debugFlag) {
        return true;
    }
    return isReady() && !INTL_FLAG;
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

function case19_3() {
    if (INTL_FLAG) {
        doIntl();
    } else {
        doLocal();
    }
    doCommon();
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

function case20_1() {
    if (INTL_FLAG) toPwd();
    else loginStrategy();
}

function case20_2() {
    if (!INTL_FLAG) doLocal();
    else doIntl();
}

// ============================================================
// Group 22: Nested ternary
// ============================================================

function case22_5(x) {
    return INTL_FLAG
        ? x > 0
            ? R_STRING_A
            : R_STRING_B
        : R_STRING_C;
}

function case22_6(x) {
    return !INTL_FLAG
        ? x > 0
            ? R_STRING_A
            : R_STRING_B
        : R_STRING_C;
}

// ============================================================
// Group 23: Switch/case boundary
// ============================================================

function case23_1(privilege) {
    switch (privilege) {
        case 1:
            if (INTL_FLAG) {
                return buildIntl(privilege);
            }
            return buildLocal(privilege);
        case 2:
            return buildUndo(privilege);
        default:
            return buildDefault(privilege);
    }
}

function case23_2(type) {
    switch (type) {
        case 1:
            if (INTL_FLAG) {
                return "intl";
            } else {
                return "local";
            }
        case 2:
            return "other";
    }
}
