package test

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
	s := "INTL_FLAG is true"
}

func case1_6() bool { return true }

func case1_7() { isIntl := true; doSomething(isIntl) }

func case1_8() { foo(true, "test") }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

func case2_1() {
}

func case2_2() {
	alive()
}

func case2_3() {
}

func case2_4() {
	alive()
}

func case2_5() {
	alive()
}

// ============================================================
// Group 3: Compound boolean (no ternary in Go)
// ============================================================

func case3_1() {
}

func case3_2() { b := false; _ = b }

func case3_3() {
	doSomething()
}

func case3_4() { b := true; _ = b }

func case3_7() {
}

func case3_8() {
	// if false && someCondition() { return }
}

func case3_9() { forceCalc = forceCalc }

func case3_10() {
	if someCondition() {
		doSomething()
	}
}

func case3_11() { b := isChinese(); _ = b }

func case3_12() {
	if someCondition() {
		doSomething()
	}
}

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

func case4_4() {
	if someCondition() {
		doB()
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

func case5_3() {
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

func case6_1() bool {
	if isGranted() {
		return true
	}
	return true
}

func case6_2() {
	doFirst()
	return
}

func case6_3() {
	panic("error")
}

func case6_5() {
	for i := 0; i < 10; i++ {
		break
	}
}

func case6_6() {
	doFirst()
	return
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

func case7_1() int {
	result := doWork()
	return result
}

func case7_3() bool {
	if startsWith(url, "sms:") {
		return true
	}
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

func case9_8() {
	if checkPermission() {
		grant()
	}
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

func case10_1() { s := "if true { do something }"; _ = s }

func case10_2() {
	// if true {
	//   doSomething()
	// } else {
	//   doOther()
	// }
	doActual()
}

func case10_4() { a = true; b = false }

func case10_5() {
	for {
		if shouldStop() {
			break
		}
		doWork()
	}
}

func case10_7() bool  { return true }
func case10_7b() bool { return false }

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

func case11_5() {
	if someCondition() {
		doA()
	} else if otherCondition() {
		doB()
	} else {
		doC()
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
	ok := check()
	_ = ok
}

func case12_3() {
}

func case12_4() {
	ok := true
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

func case13_5() {
	b := someCondition()
	_ = b
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

func case15_1() {
}

func case15_7() {
	doIntl()
}

func case15_9() bool {
	return false
}

func case16_1() {
	if local.lock == true && remote.lock == false {
		doSomething()
	}
}

func case16_2() {
	if flag == false && someCondition() {
		doSomething()
	}
}

func case16_3() {
	if someCondition() && flag == true {
		doSomething()
	}
}

// ============================================================
// Group 17: Dead code after return
// ============================================================

func case17_2() {
	setup()
	return
}

func case17_5() {
	for i := 0; i < 10; i++ {
		continue
	}
}

func case17_6() {
	return
}

func case17_7() {
	doSomething()
}

// ============================================================
// Group 18: } boundary
// ============================================================

func case18_1() bool {
	if debugBuild && debugFlag {
		return true
	}
	return false
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

func case19_1(t int) interface{} {
	return newGPComponent(t)
}

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

func case20_4() {
	doIntl()
	doMore()
	doAfter()
}

func case20_5(x int) {
	if x > 0 {
		doPositive()
	} else {
		doNegative()
	}
}

// ============================================================
// Group 23: Switch/case boundary
// ============================================================

func case23_1(privilege int) string {
	switch privilege {
	case 1:
		return buildIntl(privilege)
	case 2:
		return buildUndo(privilege)
	default:
		return buildDefault(privilege)
	}
}

func case23_2(t int) string {
	switch t {
	case 1:
		return "intl"
	case 2:
		return "other"
	}
	return ""
}

// ============================================================
// Group 24: Local constant-like bool (Go has no final; keep live uses)
// ============================================================

func case24_multiline(flag bool) {
	isOneWay :=
		false
	useBool(isOneWay)
}

func otherCheck() bool { return true }
func useBool(b bool) { println(b) }

func case19_1(t int) interface{} {
	return "gp"
}

func case20_exit() {
	setup()
	return
}
