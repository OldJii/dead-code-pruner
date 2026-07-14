package com.test

// ============================================================
// Group 1: Constant replacement
// ============================================================

fun case1_1() {
    doPrimary()
}

fun case1_2() {
    afterCode()
}

fun case1_3() {
    doPrimary()
}

fun case1_4() {
    doPrimary()
}

fun case1_5() { val s = "primary"
}

fun case1_6(): Boolean { return true }

fun case1_7() { val isPrimary = true; doSomething(isPrimary) }

fun case1_8() { foo(true, "test") }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

fun case2_1() { }

fun case2_2() { alive() }

fun case2_3() { }

fun case2_4() { alive() }

fun case2_5() { alive() }

// ============================================================
// Group 3: Compound boolean
// ============================================================

fun case3_1() {
}

fun case3_2() { val b = false }

fun case3_3() { doSomething() }

fun case3_4() { val b = true }

fun case3_7() {
}

fun case3_9() { forceCalc = forceCalc }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

fun case4_1() {
    afterCode()
}

fun case4_2() {
}

fun case4_3() {
    alive()
}

fun case4_4() {
    if (condition) {
        doSomething()
    }
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

fun case5_1() {
    doSomething()
}

fun case5_2() {
    doA()
    doB()
}

fun case5_3() {
    doPrimary()
}

fun case5_4() {
    doPrimary()
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

fun case6_1(): Boolean {
    if (isGranted()) { return true }
    return true
}

fun case6_2() {
    doFirst()
    return
}

fun case6_3() {
    throw RuntimeException("error")
}

fun case6_5() {
    for (i in 0 until 10) {
        break
    }
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

fun case7_1(): Int {
    val result = doWork()
    return result
}

fun case7_3(): Boolean {
    if (url.startsWith("sms:")) { return true }
    return false
}

// ============================================================
// Group 8: Kotlin if expressions
// ============================================================

fun case8_1() {
    selectedIdx = selectedIdx
    selectedIdx = selectedIdx.coerceAtLeast(0)
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

fun case9_1() {
    afterCode()
}

fun case9_2() {
    doB()
    afterCode()
}

fun case9_9() {
    doDeep()
    afterCode()
}

fun case9_13() {
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

fun case10_4() { a = true; b = false }

fun case10_7(): Boolean { return true }
fun case10_7b(): Boolean { return false }

fun case10_9() { setEnabled(true); setVisible(false) }

// ============================================================
// Group 11: else if (true/false)
// ============================================================

fun case11_1() {
    if (flowMode == "special") {
        doComplex()
    } else {
        toEarlyUid()
    }
}

fun case11_2() {
    if (flowMode == "special") {
        doComplex()
    } else {
        continueFlow()
    }
}

fun case11_3() {
    if (someCondition()) {
        doA()
    } else {
        doB()
    }
}

fun case11_4() {
    if (someCondition()) {
        doA()
    }
    afterCode()
}

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

fun case12_1() {
    if (notNull(data)) {
        process(data)
    }
}

fun case12_2() {
    val ok = check()
}

fun case12_3() {
}

fun case12_4() {
    val ok = true
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

fun case13_1() {
    if (equals(nextStage, localeReady)) {
        doSomething()
    }
}

fun case13_3() {
}

fun case13_4() {
    if (someCondition()) {
        doSomething()
    }
}

fun case13_5() {
    val b = someCondition()
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

fun case15_1() {
}

fun case15_7() {
    doPrimary()
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
    return
}

fun case17_5() {
    for (i in 0 until 10) {
        continue
    }
}

fun case17_6() {
    return
}

fun case17_7() {
    doSomething()
}

// ============================================================
// Group 18: } boundary
// ============================================================

fun case18_1(): Boolean {
    if (debugBuild && debugFlag) {
        return true
    }
    return false
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

fun case19_1(type: Int): Any {
    return PrimaryComponent(type)
}

fun case19_3() {
    doPrimary()
    doCommon()
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

fun case20_1() {
    toPwd()
}

fun case20_2() {
    doPrimary()
}

fun case20_5(x: Int) {
    if (x > 0) {
        doPositive()
    } else {
        doNegative()
    }
}

// ============================================================
// Group 21: Kotlin if expressions (no semicolons)
// ============================================================

fun case21_1() {
    return false
}

fun case21_2() {
    return RemoteConfig.getInstance().getBoolean(SAMPLE_REMOTE_TOGGLE)
}

fun case21_3() {
    selectedIdx = selectedIdx
    selectedIdx = selectedIdx.coerceAtLeast(0)
}

fun case21_4() {
    selectedIdx = 0
    selectedIdx = selectedIdx.coerceAtLeast(0)
}

fun case21_5() {
    val x = "primary"
    println(x)
}

fun case21_6() {
    return compute() + 1
}

// ============================================================
// Group 22: Kotlin no-semicolons
// ============================================================

fun case22_1(url: String, context: Any): Boolean {
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
    afterCode()
}

fun case22_3() {
    beforeCode()
    doAction()
    afterCode()
}

fun case22_4(): Boolean {
    return false
}

// ============================================================
// Group 23: when (Kotlin switch)
// ============================================================

fun case23_1(choice: Int): String {
    return when (choice) {
        1 -> buildPrimary(choice)
        2 -> buildUndo(choice)
        else -> buildDefault(choice)
    }
}

// ============================================================
// Group 24: 本地常量传播 (Phase 1, Step 2)
// ============================================================

fun case24_1() {
    doPrimary()
}

fun case24_2() {
    val result = "primary"
    println(result)
}

// ============================================================
// Group 25: Multi-line assignment safety
// ============================================================

fun case25_multiline(flag: Boolean) {
    useBool(false)
}

fun otherCheck(): Boolean = true
fun useBool(b: Boolean) { println(b) }

fun case25_paren() {
    if (notNull(data)) {
        process(data)
    }
}
