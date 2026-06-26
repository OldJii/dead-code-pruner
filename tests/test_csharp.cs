// C# test cases for dead-code-pruner

// ============================================================
// Group 1: Constant replacement
// ============================================================

void Case1_1() {
    if (INTL_FLAG) { DoIntl(); }
}

void Case1_2() {
    if (!INTL_FLAG) { DoDomestic(); }
    AfterCode();
}

void Case1_3() {
    if (INTL_FLAG) { DoIntl(); } else { DoDomestic(); }
}

bool Case1_6() { return INTL_FLAG; }

void Case1_7() { var isIntl = INTL_FLAG; DoSomething(isIntl); }

void Case1_8() { Foo(INTL_FLAG, "test"); }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

void Case2_1() { if (!true) { Dead(); } }

void Case2_2() { if (!false) { Alive(); } }

void Case2_3() { if (true == false) { Dead(); } }

void Case2_4() { if (true != false) { Alive(); } }

void Case2_5() { if (false == false) { Alive(); } }

// ============================================================
// Group 3: Compound boolean + ternary
// ============================================================

void Case3_1() {
    if (false && picksGuideUser) { DoSomething(); }
}

void Case3_2() { var b = IsChinese() && false; }

void Case3_3() { if (true || SomeCondition()) { DoSomething(); } }

void Case3_4() { var b = SomeCondition() || true; }

void Case3_5() { var val_ = countDownTimes % (false ? 2 : 4); }

void Case3_6() { var s = true ? "intl" : "local"; }

void Case3_9() { forceCalc = forceCalc || false; }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

void Case4_1() {
    if (false) {
        DoSomethingDead();
    }
    AfterCode();
}

void Case4_2() {
    if (false) {
        DeadCode1();
        DeadCode2();
    }
}

void Case4_3() {
    if (false) {
        Dead();
    } else {
        Alive();
    }
}

void Case4_4() {
    if (false) {
        Dead();
    } else if (condition) {
        DoSomething();
    }
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

void Case5_1() {
    if (true) {
        DoSomething();
    }
}

void Case5_2() {
    if (true) {
        DoA();
        DoB();
    }
}

void Case5_3() {
    if (true) {
        DoIntl();
    } else {
        DoDomestic();
    }
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

bool Case6_1() {
    if (IsGranted()) { return true; }
    if (true) { return true; }
    AfterCode();
    return false;
}

void Case6_2() {
    DoFirst();
    if (true) { return; }
    DoSecond();
    DoThird();
}

void Case6_3() {
    throw new Exception("error");
    Cleanup();
}

// ============================================================
// Group 7: Single-line if(false)
// ============================================================

int Case7_1() {
    if (false) return -1;
    var result = DoWork();
    return result;
}

// ============================================================
// Group 9: Nested
// ============================================================

void Case9_1() {
    if (false) {
        if (inner) { DoInner(); }
    }
    AfterCode();
}

void Case9_2() {
    if (false) { DoA(); }
    if (true) { DoB(); }
    AfterCode();
}

void Case9_4() { Foo(true ? 4 : 2, true ? "intl" : "local"); }

void Case9_13() {
    if (false) { Dead1(); }
    if (false) { Dead2(); }
    if (false) { Dead3(); }
    Alive();
}

// ============================================================
// Group 10: Edge cases
// ============================================================

void Case10_1() { var s = "if (true) { do something }"; }

void Case10_4() { a = !false; b = !true; }

bool Case10_7() { return true; }
bool Case10_7b() { return false; }

void Case10_9() { SetEnabled(true); SetVisible(false); }

// ============================================================
// Group 11: else if (true/false)
// ============================================================

void Case11_1() {
    if (signUpType == "cosmos") {
        DoComplex();
    } else if (true) {
        ToEarlyUid();
    } else {
        ToSignUp();
    }
}

void Case11_2() {
    if (signUpType == "cosmos") {
        DoComplex();
    } else if (false) {
        DoDead();
    } else {
        ToSignUp();
    }
}

void Case11_4() {
    if (SomeCondition()) {
        DoA();
    } else if (false) {
        DoDead();
    }
    AfterCode();
}

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

void Case12_1() {
    if (NotNull(data) && (true)) {
        Process(data);
    }
}

void Case12_2() {
    var ok = Check() || (false);
}

void Case12_3() {
    if ((false) && SomeCheck()) {
        Dead();
    }
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

void Case13_1() {
    if (true
        && SomeCondition()) {
        DoSomething();
    }
}

void Case13_3() {
    if (false
        && SomeCondition()
        && AnotherCondition()) {
        DoSomething();
    }
}

// ============================================================
// Group 14: Cross-line ternary
// ============================================================

void Case14_1() {
    var cb =
        true
            ? CreateCallbackA()
            : CreateCallbackB();
}

void Case14_2() {
    var label =
        false
            ? "suggested"
            : "recommended";
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

void Case15_1() {
    if (position == 0 && !INTL_FLAG) {
        DoSomething();
    }
}

void Case15_7() {
    if (position == 0 || INTL_FLAG) {
        DoIntl();
    }
}

void Case16_1() {
    if (local.Lock == true && remote.Lock == false) {
        DoSomething();
    }
}

// ============================================================
// Group 17: Dead code after return
// ============================================================

void Case17_2() {
    Setup();
    if (INTL_FLAG) return;
    DoSomethingA();
    DoSomethingB();
}

void Case17_6() {
    if (INTL_FLAG) return;
}

void Case17_7() {
    if (!INTL_FLAG) return;
    DoSomething();
}

// ============================================================
// Group 18: } boundary
// ============================================================

bool Case18_1() {
    if (debugBuild && debugFlag) {
        return true;
    }
    return IsReady() && !INTL_FLAG;
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

void Case19_3() {
    if (INTL_FLAG) {
        DoIntl();
    } else {
        DoLocal();
    }
    DoCommon();
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

void Case20_1() {
    if (INTL_FLAG) ToPwd();
    else LoginStrategy();
}

void Case20_2() {
    if (!INTL_FLAG) DoLocal();
    else DoIntl();
}

// ============================================================
// Group 22: Nested ternary
// ============================================================

int Case22_5(int x) {
    return INTL_FLAG
        ? x > 0
            ? R_STRING_A
            : R_STRING_B
        : R_STRING_C;
}

// ============================================================
// Group 23: Switch/case boundary
// ============================================================

int Case23_1(int type) {
    switch (type) {
        case 1:
            if (INTL_FLAG) {
                return BuildIntl(type);
            }
            return BuildLocal(type);
        case 2:
            return BuildOther(type);
        default:
            return BuildDefault(type);
    }
}
