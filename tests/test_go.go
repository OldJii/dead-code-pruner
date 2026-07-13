package test

// ============================================================
// Group 1: Constant replacement
// ============================================================

func case1_1() {
	if FEATURE_FLAG {
		doPrimary()
	}
}

func case1_2() {
	if !FEATURE_FLAG {
		doSecondary()
	}
	afterCode()
}

func case1_3() {
	if FEATURE_FLAG && act == sampleActivity {
		showFrom = "primary"
	}
}

func case1_4() {
	// if FEATURE_FLAG { ... }
	/* FEATURE_FLAG check */
}

func case1_5() {
	s := "FEATURE_FLAG is true"
}

func case1_6() bool { return FEATURE_FLAG }

func case1_7() { isPrimary := FEATURE_FLAG; doSomething(isPrimary) }

func case1_8() { foo(FEATURE_FLAG, "test") }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

func case2_1() {
	if !true {
		dead()
	}
}

func case2_2() {
	if !false {
		alive()
	}
}

func case2_3() {
	if true == false {
		dead()
	}
}

func case2_4() {
	if true != false {
		alive()
	}
}

func case2_5() {
	if false == false {
		alive()
	}
}

// ============================================================
// Group 3: Compound boolean (no ternary in Go)
// ============================================================

func case3_1() {
	if false && paramsHolder.cardData.getUserInfo().picksGuideUser {
		doSomething()
	}
}

func case3_2() { b := isChinese() && false; _ = b }

func case3_3() {
	if true || someCondition() {
		doSomething()
	}
}

func case3_4() { b := someCondition() || true; _ = b }

func case3_7() {
	if false && !isEmpty(identifier) && contains(identifier, "guideNewUser") {
		doSomething()
	}
}

func case3_8() {
	// if false && someCondition() { return }
}

func case3_9() { forceCalc = forceCalc || false }

func case3_10() {
	if true && someCondition() {
		doSomething()
	}
}

func case3_11() { b := isChinese() && true; _ = b }

func case3_12() {
	if false || someCondition() {
		doSomething()
	}
}

// ============================================================
// Group 4: if(false) block removal
// ============================================================

func case4_1() {
	if false {
		deadCode()
	}
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

func case4_4() {
	if false {
		deadCode()
	} else if someCondition() {
		doB()
	}
	afterCode()
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

func case5_1() {
	if true {
		doA()
	}
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

func case5_3() {
	if true {
		doA()
	} else if someCondition() {
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

func case6_1() bool {
	if isGranted() {
		return true
	}
	if true {
		return true
	}
	return isAllGranted()
}

func case6_2() {
	doFirst()
	if true {
		return
	}
	doSecond()
	doThird()
}

func case6_3() {
	if true {
		panic("error")
	}
	cleanup()
}

func case6_5() {
	for i := 0; i < 10; i++ {
		if true {
			break
		}
		processItem(i)
	}
}

func case6_6() {
	doFirst()
	if true {
		return
	}
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

func case7_1() int {
	if false {
		return -1
	}
	result := doWork()
	return result
}

func case7_3() bool {
	if false {
		return false
	}
	if startsWith(url, "sms:") {
		return true
	}
	return false
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

func case9_1() {
	if false {
		if true {
			doA()
		}
		doB()
	}
	afterCode()
}

func case9_2() {
	if false {
		doA()
	}
	if true {
		doB()
	}
	afterCode()
}

func case9_8() {
	if true && checkPermission() {
		grant()
	}
}

func case9_9() {
	if true {
		if true {
			doDeep()
		}
	}
	afterCode()
}

func case9_13() {
	if false {
		dead1()
	}
	if false {
		dead2()
	}
	if false {
		dead3()
	}
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

func case10_4() { a = !false; b = !true }

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
	if flowMode == special {
		doComplex()
	} else if true {
		toEarlyUid()
	} else {
		continueFlow()
	}
}

func case11_2() {
	if flowMode == special {
		doComplex()
	} else if false {
		doDead()
	} else {
		continueFlow()
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

func case11_5() {
	if someCondition() {
		doA()
	} else if false {
		doDead()
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
	if notNull(data) && (true) {
		process(data)
	}
}

func case12_2() {
	ok := check() || (false)
	_ = ok
}

func case12_3() {
	if (false) && someCheck() {
		dead()
	}
}

func case12_4() {
	ok := (true) || someCondition()
	_ = ok
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

func case13_1() {
	if true &&
		equals(nextStage, localeReady) {
		doSomething()
	}
}

func case13_3() {
	if false &&
		someCondition() &&
		anotherCondition() {
		doSomething()
	}
}

func case13_4() {
	if someCondition() &&
		true {
		doSomething()
	}
}

func case13_5() {
	b := someCondition() ||
		false
	_ = b
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

func case15_1() {
	if position == 0 && !FEATURE_FLAG {
		doSomething()
	}
}

func case15_7() {
	if position == 0 || FEATURE_FLAG {
		doPrimary()
	}
}

func case15_9() bool {
	return position == 0 && !FEATURE_FLAG
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
	if FEATURE_FLAG {
		return
	}
	doSomethingA()
	doSomethingB()
}

func case17_5() {
	for i := 0; i < 10; i++ {
		if FEATURE_FLAG {
			continue
		}
		doSomething(i)
	}
}

func case17_6() {
	if FEATURE_FLAG {
		return
	}
}

func case17_7() {
	if !FEATURE_FLAG {
		return
	}
	doSomething()
}

// ============================================================
// Group 18: } boundary
// ============================================================

func case18_1() bool {
	if debugBuild && debugFlag {
		return true
	}
	return isReady() && !FEATURE_FLAG
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

func case19_1(t int) interface{} {
	if FEATURE_FLAG {
		return newPrimaryComponent(t)
	} else if t == 1 {
		return newSecondaryComponent(t)
	}
	return newDefaultComponent(t)
}

func case19_3() {
	if FEATURE_FLAG {
		doPrimary()
	} else {
		doLocal()
	}
	doCommon()
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

func case20_1() {
	if FEATURE_FLAG {
		toPwd()
	} else {
		loginStrategy()
	}
}

func case20_2() {
	if !FEATURE_FLAG {
		doLocal()
	} else {
		doPrimary()
	}
}

func case20_3() {
	setup()
	if FEATURE_FLAG {
		return
	} else {
		doLocal()
	}
	doAfter()
}

func case20_4() {
	if !FEATURE_FLAG {
		return
	} else {
		doPrimary()
		doMore()
	}
	doAfter()
}

func case20_5(x int) {
	if !FEATURE_FLAG {
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

func case23_1(choice int) string {
	switch choice {
	case 1:
		if FEATURE_FLAG {
			return buildPrimary(choice)
		}
		return buildSecondary(choice)
	case 2:
		return buildUndo(choice)
	default:
		return buildDefault(choice)
	}
}

func case23_2(t int) string {
	switch t {
	case 1:
		if FEATURE_FLAG {
			return "primary"
		} else {
			return "secondary"
		}
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
		!FEATURE_FLAG &&
			flag &&
			otherCheck()
	useBool(isOneWay)
}

func otherCheck() bool { return true }
func useBool(b bool) { println(b) }

func case19_1(t int) interface{} {
	if FEATURE_FLAG {
		return "gp"
	} else if t == 1 {
		return "secondary"
	}
	return "default"
}

func case20_exit() {
	setup()
	if FEATURE_FLAG {
		return
	}
	doAfter()
}
