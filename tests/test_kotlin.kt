package com.test

// ============================================================
// Group 1: Constant replacement
// ============================================================

fun case1_1() {
    if (INTL_FLAG) { doIntl() }
}

fun case1_2() {
    if (!INTL_FLAG) { doDomestic() }
    afterCode()
}

fun case1_3() {
    if (INTL_FLAG) { doIntl() } else { doDomestic() }
}

fun case1_4() {
    if (!INTL_FLAG) { doDomestic() } else { doIntl() }
}

fun case1_5() { val s = if (INTL_FLAG) "intl" else "local" }

fun case1_6(): Boolean { return INTL_FLAG }

fun case1_7() { val isIntl = INTL_FLAG; doSomething(isIntl) }

fun case1_8() { foo(INTL_FLAG, "test") }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

fun case2_1() { if (!true) { dead() } }

fun case2_2() { if (!false) { alive() } }

fun case2_3() { if (true == false) { dead() } }

fun case2_4() { if (true != false) { alive() } }

fun case2_5() { if (false == false) { alive() } }

// ============================================================
// Group 3: Compound boolean
// ============================================================

fun case3_1() {
    if (false && picksGuideUser) { doSomething() }
}

fun case3_2() { val b = isChinese() && false }

fun case3_3() { if (true || someCondition()) { doSomething() } }

fun case3_4() { val b = someCondition() || true }

fun case3_7() {
    if (false && !isEmpty(identifier) && contains(identifier, "guideNewUser")) {
        doSomething()
    }
}

fun case3_9() { forceCalc = forceCalc || false }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

fun case4_1() {
    if (false) {
        doSomethingDead()
    }
    afterCode()
}

fun case4_2() {
    if (false) {
        deadCode1()
        deadCode2()
    }
}

fun case4_3() {
    if (false) {
        dead()
    } else {
        alive()
    }
}

fun case4_4() {
    if (false) {
        dead()
    } else if (condition) {
        doSomething()
    }
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

fun case5_1() {
    if (true) {
        doSomething()
    }
}

fun case5_2() {
    if (true) {
        doA()
        doB()
    }
}

fun case5_3() {
    if (true) {
        doIntl()
    } else {
        doDomestic()
    }
}

fun case5_4() {
    if (true) {
        doIntl()
    } else if (condition) {
        doOther()
    } else {
        doDefault()
    }
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

fun case6_1(): Boolean {
    if (isGranted()) { return true }
    if (true) { return true }
    afterCode()
    return false
}

fun case6_2() {
    doFirst()
    if (true) { return }
    doSecond()
    doThird()
}

fun case6_3() {
    throw RuntimeException("error")
    cleanup()
}

fun case6_5() {
    for (i in 0 until 10) {
        break
        processItem(i)
    }
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

fun case7_1(): Int {
    if (false) return -1
    val result = doWork()
    return result
}

fun case7_3(): Boolean {
    if (false) return false
    if (url.startsWith("sms:")) { return true }
    return false
}

// ============================================================
// Group 8: Kotlin if expressions
// ============================================================

fun case8_1() {
    selectedIdx =
      if (false) 0 else selectedIdx
    selectedIdx = selectedIdx.coerceAtLeast(0)
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

fun case9_1() {
    if (false) {
        if (inner) { doInner() }
    }
    afterCode()
}

fun case9_2() {
    if (false) { doA() }
    if (true) { doB() }
    afterCode()
}

fun case9_9() {
    if (true) {
        if (true) { doDeep() }
    }
    afterCode()
}

fun case9_13() {
    if (false) { dead1() }
    if (false) { dead2() }
    if (false) { dead3() }
    alive()
}

// ============================================================
// Group 10: Edge cases and safety
// ============================================================

fun case10_1() { val s = "if (true) { do something }" }

fun case10_2() {
    // if (true) {
    //   doSomething()
    // }
    doActual()
}

fun case10_4() { a = !false; b = !true }

fun case10_7(): Boolean { return true }
fun case10_7b(): Boolean { return false }

fun case10_9() { setEnabled(true); setVisible(false) }

// ============================================================
// Group 11: else if (true/false)
// ============================================================

fun case11_1() {
    if (signUpType == "cosmos") {
        doComplex()
    } else if (true) {
        toEarlyUid()
    } else {
        toSignUp()
    }
}

fun case11_2() {
    if (signUpType == "cosmos") {
        doComplex()
    } else if (false) {
        doDead()
    } else {
        toSignUp()
    }
}

fun case11_3() {
    if (someCondition()) {
        doA()
    } else if (true) {
        doB()
    }
}

fun case11_4() {
    if (someCondition()) {
        doA()
    } else if (false) {
        doDead()
    }
    afterCode()
}

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

fun case12_1() {
    if (notNull(data) && (true)) {
        process(data)
    }
}

fun case12_2() {
    val ok = check() || (false)
}

fun case12_3() {
    if ((false) && someCheck()) {
        dead()
    }
}

fun case12_4() {
    val ok = (true) || someCondition()
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

fun case13_1() {
    if (true
        && equals(nextStage, ethnicitySaved)) {
        doSomething()
    }
}

fun case13_3() {
    if (false
        && someCondition()
        && anotherCondition()) {
        doSomething()
    }
}

fun case13_4() {
    if (someCondition() &&
        true) {
        doSomething()
    }
}

fun case13_5() {
    val b = someCondition()
        || false
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

fun case15_1() {
    if (position == 0 && !INTL_FLAG) {
        doSomething()
    }
}

fun case15_7() {
    if (position == 0 || INTL_FLAG) {
        doIntl()
    }
}

fun case16_1() {
    if (local.lock == true
        && remote.lock == false) {
        doSomething()
    }
}

fun case16_2() {
    if (flag == false && someCondition()) {
        doSomething()
    }
}

// ============================================================
// Group 17: Dead code after return
// ============================================================

fun case17_2() {
    setup()
    if (INTL_FLAG) return
    doSomethingA()
    doSomethingB()
}

fun case17_5() {
    for (i in 0 until 10) {
        if (INTL_FLAG) continue
        doSomething(i)
    }
}

fun case17_6() {
    if (INTL_FLAG) return
}

fun case17_7() {
    if (!INTL_FLAG) return
    doSomething()
}

// ============================================================
// Group 18: } boundary
// ============================================================

fun case18_1(): Boolean {
    if (debugBuild && debugFlag) {
        return true
    }
    return isReady() && !INTL_FLAG
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

fun case19_1(type: Int): Any {
    if (INTL_FLAG) {
        return GPComponent(type)
    } else if (type == 1) {
        return LocalComponent(type)
    }
    return DefaultComponent(type)
}

fun case19_3() {
    if (INTL_FLAG) {
        doIntl()
    } else {
        doLocal()
    }
    doCommon()
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

fun case20_1() {
    if (INTL_FLAG) toPwd()
    else loginStrategy()
}

fun case20_2() {
    if (!INTL_FLAG) doLocal()
    else doIntl()
}

fun case20_5(x: Int) {
    if (!INTL_FLAG) doLocal()
    else if (x > 0) {
        doPositive()
    } else {
        doNegative()
    }
}

// ============================================================
// Group 21: Kotlin if expressions (no semicolons)
// ============================================================

fun case21_1() {
    return if (INTL_FLAG) {
        false
    } else RemoteConfig.getInstance().getBoolean(ALL_MY_LIKES_SHOW)
}

fun case21_2() {
    return if (!INTL_FLAG) {
        false
    } else RemoteConfig.getInstance().getBoolean(ALL_MY_LIKES_SHOW)
}

fun case21_3() {
    selectedIdx =
      if (!INTL_FLAG) 0 else selectedIdx
    selectedIdx = selectedIdx.coerceAtLeast(0)
}

fun case21_4() {
    selectedIdx =
      if (INTL_FLAG) 0 else selectedIdx
    selectedIdx = selectedIdx.coerceAtLeast(0)
}

fun case21_5() {
    val x = if (!INTL_FLAG) "local" else "intl"
    println(x)
}

fun case21_6() {
    return if (INTL_FLAG) {
        compute() + 1
    } else defaultValue()
}

// ============================================================
// Group 22: Kotlin no-semicolons
// ============================================================

fun case22_1(url: String, context: Any): Boolean {
    if (!INTL_FLAG) return false
    if (url.startsWith("sms:") || url.startsWith("smsto:")) {
        try {
            val sendIntent = createIntent(url)
            context.startActivity(sendIntent)
        } catch (e: Exception) {
            reportError(e)
        }
        return true
    }
    return false
}

fun case22_2() {
    beforeCode()
    if (!INTL_FLAG) doSomething()
    afterCode()
}

fun case22_3() {
    beforeCode()
    if (INTL_FLAG) doAction()
    afterCode()
}

fun case22_4(): Boolean {
    if (INTL_FLAG) return false
    val result = compute()
    return result > 0
}

// ============================================================
// Group 23: when (Kotlin switch)
// ============================================================

fun case23_1(privilege: Int): String {
    return when (privilege) {
        1 -> if (INTL_FLAG) buildIntl(privilege) else buildLocal(privilege)
        2 -> buildUndo(privilege)
        else -> buildDefault(privilege)
    }
}

// ============================================================
// Group 24: 本地常量传播 (Step 1b)
// ============================================================

fun case24_1() {
    val isIntl = INTL_FLAG
    if (isIntl) {
        doIntl()
    } else {
        doLocal()
    }
}

fun case24_2() {
    val flag: Boolean = INTL_FLAG
    val result = if (flag) "intl" else "local"
    println(result)
}

// ============================================================
// Group 25: Multi-line assignment safety
// ============================================================

fun case25_multiline(flag: Boolean) {
    val isOneWay =
        !INTL_FLAG
            && flag
            && otherCheck()
    useBool(isOneWay)
}

fun otherCheck(): Boolean = true
fun useBool(b: Boolean) { println(b) }

fun case25_paren() {
    if (notNull(data) && (true)) {
        process(data)
    }
}
