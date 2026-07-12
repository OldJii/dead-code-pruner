import Foundation

// ============================================================
// Group 1: Constant replacement
// ============================================================

func case1_1() {
    doIntl()
}

func case1_2() {
    afterCode()
}

func case1_3() {
    if act == fakeLikersAct {
        showFrom = "intl"
    }
}

func case1_4() {
    // if INTL_FLAG { ... }
    /* INTL_FLAG check */
}

func case1_5() {
    let s = "INTL_FLAG is true"
}

func case1_6() -> Bool { return true }

func case1_7() { let isIntl = true; doSomething(isIntl) }

func case1_8() { foo(true, "test") }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

func case2_1() { }

func case2_2() { alive() }

func case2_3() { }

func case2_4() { alive() }

func case2_5() { alive() }

// ============================================================
// Group 3: Compound boolean
// ============================================================

func case3_1() {
}

func case3_2() { let b = false }

func case3_3() { doSomething() }

func case3_4() { let b = true }

func case3_7() {
}

func case3_8() {
    // if false && someCondition() { return }
}

func case3_9() { forceCalc = forceCalc }

func case3_10() { if someCondition() { doSomething() } }

func case3_11() { let b = isChinese() }

func case3_12() { if someCondition() { doSomething() } }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

func case4_1() {
    afterCode()
}

func case4_2() {
    doElse()
}

func case4_3() {
    if someCondition() {
        doB()
    } else {
        doC()
    }
    afterCode()
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

func case5_1() {
    doA()
    afterCode()
}

func case5_2() {
    doA()
    afterCode()
}

func case5_4() {
    doA()
    afterCode()
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

func case6_1() -> Bool {
    if isGranted() { return true }
    return true
}

func case6_2() {
    doFirst()
    return
}

func case6_5() {
    for i in 0..<10 {
        break
    }
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

func case7_1() -> Int {
    let result = doWork()
    return result
}

func case7_3() -> Bool {
    if url.hasPrefix("sms:") { return true }
    return false
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

func case9_1() {
    afterCode()
}

func case9_2() {
    doB()
    afterCode()
}

func case9_9() {
    doDeep()
    afterCode()
}

func case9_13() {
    alive()
}

// ============================================================
// Group 10: Edge cases and safety
// ============================================================

func case10_1() { let s = "if true { do something }" }

func case10_2() {
    // if true {
    //   doSomething()
    // }
    doActual()
}

func case10_4() { a = true; b = false }

func case10_7() -> Bool { return true }
func case10_7b() -> Bool { return false }

func case10_9() { setEnabled(true); setVisible(false) }

// ============================================================
// Group 11: else if (true/false)
// ============================================================

func case11_1() {
    if signUpType == cosmos {
        doComplex()
    } else {
        toEarlyUid()
    }
}

func case11_2() {
    if signUpType == cosmos {
        doComplex()
    } else {
        toSignUp()
    }
}

func case11_3() {
    if someCondition() {
        doA()
    } else {
        doB()
    }
}

func case11_4() {
    if someCondition() {
        doA()
    }
    afterCode()
}

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

func case12_1() {
    if notNull(data) {
        process(data)
    }
}

func case12_2() {
    let ok = check()
    _ = ok
}

func case12_3() {
}

func case12_4() {
    let ok = true
    _ = ok
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

func case13_1() {
    if equals(nextStage, ethnicitySaved) {
        doSomething()
    }
}

func case13_3() {
}

func case13_4() {
    if someCondition() {
        doSomething()
    }
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

func case15_1() {
}

func case15_7() {
    doIntl()
}

func case16_1() {
    if (local.lock == true) && (remote.lock == false) {
        doSomething()
    }
}

func case16_2() {
    if (flag == false) && someCondition() {
        doSomething()
    }
}

// ============================================================
// Group 18: } boundary
// ============================================================

func case18_1() -> Bool {
    if debugBuild && debugFlag {
        return true
    }
    return false
}

func case18_4() {
    for i in 0..<10 {
        process(i)
    }
    _ = false
}

// ============================================================
// Group 17: Dead code after return
// ============================================================

func case17_2() {
    setup()
    return
}

func case17_6() {
    return
}

func case17_7() {
    doSomething()
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

func case19_3() {
    doIntl()
    doCommon()
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

func case20_1() {
    toPwd()
}

func case20_2() {
    doIntl()
}

func case20_3() {
    setup()
    return
}

func case20_5(x: Int) {
    if x > 0 {
        doPositive()
    } else {
        doNegative()
    }
}

// ============================================================
// Group 23: Switch/case boundary
// ============================================================

func case23_1(privilege: Int) -> String {
    switch privilege {
    case 1:
        return buildIntl(privilege)
    case 2:
        return buildUndo(privilege)
    default:
        return buildDefault(privilege)
    }
}

func case23_2(t: Int) -> String {
    switch t {
    case 1:
        return "intl"
    case 2:
        return "other"
    default:
        return ""
    }
}

// ============================================================
// Group 24: Local let propagation
// ============================================================

func case24_1() {
    doIntl()
}

func case24_multiline(flag: Bool) {
    useBool(false)
}

func otherCheck() -> Bool { return true }
func useBool(_ b: Bool) { print(b) }
