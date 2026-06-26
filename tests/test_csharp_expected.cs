// C# test cases for dead-code-pruner

// ============================================================
// Group 1: Constant replacement
// ============================================================

void Case1_1() {
    DoIntl();
}

void Case1_2() {
    if (!true) { DoDomestic(); }
    AfterCode();
}

void Case1_3() {
    DoIntl();
}

bool Case1_6() { return true; }

void Case1_7() { var isIntl = true; DoSomething(isIntl); }

void Case1_8() { Foo(true, "test"); }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

void Case2_1() { if (!true) { Dead(); } }

void Case2_2() { if (!false) { Alive(); } }

void Case2_3() { }

void Case2_4() { Alive(); }

void Case2_5() { Alive(); }

// ============================================================
// Group 3: Compound boolean + ternary
// ============================================================

void Case3_1() {
}

void Case3_2() { var b = false; }

void Case3_3() { DoSomething(); }

void Case3_4() { var b = true; }

void Case3_5() { var val_ = countDownTimes % (4); }

void Case3_6() { var s = "intl"; }

void Case3_9() { forceCalc = forceCalc; }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

void Case4_1() {
    AfterCode();
}

void Case4_2() {
}

void Case4_3() {
    Alive();
}

void Case4_4() {
    if (condition) {
        DoSomething();
    }
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

void Case5_1() {
    DoSomething();
}

void Case5_2() {
    DoA();
    DoB();
}

void Case5_3() {
    DoIntl();
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

bool Case6_1() {
    if (IsGranted()) { return true; }
    return true;
}

void Case6_2() {
    DoFirst();
    return;
}

void Case6_3() {
    throw new Exception("error");
    Cleanup();
}

// ============================================================
// Group 7: Single-line if(false)
// ============================================================

int Case7_1() {
    var result = DoWork();
    return result;
}

// ============================================================
// Group 9: Nested
// ============================================================

void Case9_1() {
    AfterCode();
}

void Case9_2() {
    DoB();
    AfterCode();
}

void Case9_4() { Foo(4, "intl"); }

void Case9_13() {
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
    } else {
        ToEarlyUid();
    }
}

void Case11_2() {
    if (signUpType == "cosmos") {
        DoComplex();
    } else {
        ToSignUp();
    }
}

void Case11_4() {
    if (SomeCondition()) {
        DoA();
    }
    AfterCode();
}

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

void Case12_1() {
    if (NotNull(data)) {
        Process(data);
    }
}

void Case12_2() {
    var ok = Check();
}

void Case12_3() {
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

void Case13_1() {
    if (SomeCondition()) {
        DoSomething();
    }
}

void Case13_3() {
}

// ============================================================
// Group 14: Cross-line ternary
// ============================================================

void Case14_1() {
    var cb =
        CreateCallbackA();
}

void Case14_2() {
    var label =
        "recommended";
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

void Case15_1() {
    if (position == 0 && !true) {
        DoSomething();
    }
}

void Case15_7() {
    DoIntl();
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
    return;
}

void Case17_6() {
    return;
}

void Case17_7() {
    if (!true) return;
    DoSomething();
}

// ============================================================
// Group 18: } boundary
// ============================================================

bool Case18_1() {
    if (debugBuild && debugFlag) {
        return true;
    }
    return IsReady() && !true;
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

void Case19_3() {
    DoIntl();
    DoCommon();
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

void Case20_1() {
    ToPwd();
}

void Case20_2() {
    if (!true) DoLocal();
    else DoIntl();
}

// ============================================================
// Group 22: Nested ternary
// ============================================================

int Case22_5(int x) {
    return x > 0
            ? R_STRING_A
            : R_STRING_B;
}

// ============================================================
// Group 23: Switch/case boundary
// ============================================================

int Case23_1(int type) {
    switch (type) {
        case 1:
            return BuildIntl(type);
        case 2:
            return BuildOther(type);
        default:
            return BuildDefault(type);
    }
}
