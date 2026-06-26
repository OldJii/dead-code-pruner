import Foundation

// ============================================================
// Group 1: Constant replacement
// ============================================================

func case1_1() {
    if INTL_FLAG { doIntl() }
}

func case1_2() {
    if !INTL_FLAG { doDomestic() }
    afterCode()
}

func case1_3() {
    if INTL_FLAG && act == fakeLikersAct {
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

func case1_6() -> Bool { return INTL_FLAG }

func case1_7() { let isIntl = INTL_FLAG; doSomething(isIntl) }

func case1_8() { foo(INTL_FLAG, "test") }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

func case2_1() { if !true { dead() } }

func case2_2() { if !false { alive() } }

func case2_3() { if true == false { dead() } }

func case2_4() { if true != false { alive() } }

func case2_5() { if false == false { alive() } }

// ============================================================
// Group 3: Compound boolean
// ============================================================

func case3_1() {
    if false && picksGuideUser { doSomething() }
}

func case3_2() { let b = isChinese() && false }

func case3_3() { if true || someCondition() { doSomething() } }

func case3_4() { let b = someCondition() || true }

func case3_7() {
    if false && !isEmpty(identifier) && contains(identifier, "guideNewUser") {
        doSomething()
    }
}

func case3_8() {
    // if false && someCondition() { return }
}

func case3_9() { forceCalc = forceCalc || false }

func case3_10() { if true && someCondition() { doSomething() } }

func case3_11() { let b = isChinese() && true }

func case3_12() { if false || someCondition() { doSomething() } }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

func case4_1() {
    if false { deadCode() }
    afterCode()
}

func case4_2() {
    if false {
        deadCode()
    } else {
        doElse()
    }
}

func case4_3() {
    if false {
        deadCode()
    } else if someCondition() {
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
    if true { doA() }
    afterCode()
}

func case5_2() {
    if true {
        doA()
    } else {
        doB()
    }
    afterCode()
}

func case5_4() {
    if true {
        doA()
    } else if someCondition() {
        doB()
    } else {
        doC()
    }
    afterCode()
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

func case6_1() -> Bool {
    if isGranted() { return true }
    if true { return true }
    return isAllGranted()
}

func case6_2() {
    doFirst()
    if true { return }
    doSecond()
    doThird()
}

func case6_5() {
    for i in 0..<10 {
        if true { break }
        processItem(i)
    }
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

func case7_1() -> Int {
    if false { return -1 }
    let result = doWork()
    return result
}

func case7_3() -> Bool {
    if false { return false }
    if url.hasPrefix("sms:") { return true }
    return false
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

func case9_1() {
    if false {
        if true { doA() }
        doB()
    }
    afterCode()
}

func case9_2() {
    if false { doA() }
    if true { doB() }
    afterCode()
}

func case9_9() {
    if true {
        if true { doDeep() }
    }
    afterCode()
}

func case9_13() {
    if false { dead1() }
    if false { dead2() }
    if false { dead3() }
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

func case10_4() { a = !false; b = !true }

func case10_7() -> Bool { return true }
func case10_7b() -> Bool { return false }

func case10_9() { setEnabled(true); setVisible(false) }

// ============================================================
// Group 11: else if (true/false)
// ============================================================

func case11_1() {
    if signUpType == cosmos {
        doComplex()
    } else if true {
        toEarlyUid()
    } else {
        toSignUp()
    }
}

func case11_2() {
    if signUpType == cosmos {
        doComplex()
    } else if false {
        doDead()
    } else {
        toSignUp()
    }
}

func case11_3() {
    if someCondition() {
        doA()
    } else if true {
        doB()
    }
}

func case11_4() {
    if someCondition() {
        doA()
    } else if false {
        doDead()
    }
    afterCode()
}

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

func case12_1() {
    if notNull(data) && (true) {
        process(data)
    }
}

func case12_2() {
    let ok = check() || (false)
    _ = ok
}

func case12_3() {
    if (false) && someCheck() {
        dead()
    }
}

func case12_4() {
    let ok = (true) || someCondition()
    _ = ok
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

func case13_1() {
    if true
        && equals(nextStage, ethnicitySaved) {
        doSomething()
    }
}

func case13_3() {
    if false
        && someCondition()
        && anotherCondition() {
        doSomething()
    }
}

func case13_4() {
    if someCondition() &&
        true {
        doSomething()
    }
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

func case15_1() {
    if (position == 0) && !INTL_FLAG {
        doSomething()
    }
}

func case15_7() {
    if (position == 0) || INTL_FLAG {
        doIntl()
    }
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
    return isReady() && !INTL_FLAG
}

func case18_4() {
    for i in 0..<10 {
        process(i)
    }
    let result = compute() && !INTL_FLAG
    _ = result
}

// ============================================================
// Group 17: Dead code after return
// ============================================================

func case17_2() {
    setup()
    if INTL_FLAG { return }
    doSomethingA()
    doSomethingB()
}

func case17_6() {
    if INTL_FLAG { return }
}

func case17_7() {
    if !INTL_FLAG { return }
    doSomething()
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

func case19_3() {
    if INTL_FLAG {
        doIntl()
    } else {
        doLocal()
    }
    doCommon()
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

func case20_1() {
    if INTL_FLAG {
        toPwd()
    } else {
        loginStrategy()
    }
}

func case20_2() {
    if !INTL_FLAG {
        doLocal()
    } else {
        doIntl()
    }
}

func case20_3() {
    setup()
    if INTL_FLAG {
        return
    } else {
        doLocal()
    }
    doAfter()
}

func case20_5(x: Int) {
    if !INTL_FLAG {
        doLocal()
    } else if x > 0 {
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
        if INTL_FLAG {
            return buildIntl(privilege)
        }
        return buildLocal(privilege)
    case 2:
        return buildUndo(privilege)
    default:
        return buildDefault(privilege)
    }
}

func case23_2(t: Int) -> String {
    switch t {
    case 1:
        if INTL_FLAG {
            return "intl"
        } else {
            return "local"
        }
    case 2:
        return "other"
    default:
        return ""
    }
}
