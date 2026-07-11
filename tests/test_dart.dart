// ============================================================
// Group 1: Constant folding
// ============================================================

void case1_1() {
  if (BuildConfig.IS_PRODUCTION) {
    doIntl();
  }
}

void case1_2() {
  if (!BuildConfig.IS_PRODUCTION) {
    doLocal();
  }
}

bool case1_3() {
  return BuildConfig.IS_PRODUCTION;
}

void case1_4() {
  var s = BuildConfig.IS_PRODUCTION ? "intl" : "local";
  print(s);
}

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

void case2_1() {
  if (BuildConfig.IS_PRODUCTION && false) {
    doSomething();
  }
}

void case2_2() {
  if (BuildConfig.IS_PRODUCTION && alive()) {
    doSomething();
  }
}

void case2_3() {
  if (!BuildConfig.IS_PRODUCTION || false) {
    doSomething();
  }
}

void case2_4() {
  if (!BuildConfig.IS_PRODUCTION || alive()) {
    doSomething();
  }
}

// ============================================================
// Group 3: Compound boolean + ternary
// ============================================================

void case3_1() {
  var x = BuildConfig.IS_PRODUCTION ? "intl" : "local";
  print(x);
}

void case3_2() {
  var x = !BuildConfig.IS_PRODUCTION ? "local" : "intl";
  print(x);
}

// ============================================================
// Group 4: if(false) block removal
// ============================================================

void case4_1() {
  if (!BuildConfig.IS_PRODUCTION) {
    doLocal();
  }
  afterCode();
}

void case4_2() {
  if (!BuildConfig.IS_PRODUCTION) {
    doLocal();
  }
}

void case4_3() {
  if (!BuildConfig.IS_PRODUCTION) {
    doLocal();
  } else {
    alive();
  }
}

void case4_4() {
  if (!BuildConfig.IS_PRODUCTION) {
    doLocal();
  } else if (condition) {
    doSomething();
  }
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

void case5_1() {
  if (BuildConfig.IS_PRODUCTION) {
    doSomething();
  }
}

void case5_2() {
  if (BuildConfig.IS_PRODUCTION) {
    doA();
    doB();
  }
}

void case5_3() {
  if (BuildConfig.IS_PRODUCTION) {
    doIntl();
  } else {
    doLocal();
  }
}

// ============================================================
// Group 6: Dead code removal after exit
// ============================================================

bool case6_1() {
  if (isGranted()) { return true; }
  if (BuildConfig.IS_PRODUCTION) { return true; }
  return false;
}

void case6_2() {
  doFirst();
  if (BuildConfig.IS_PRODUCTION) { return; }
  doSecond();
}

// ============================================================
// Group 7: Nested and complex
// ============================================================

void case7_1() {
  if (BuildConfig.IS_PRODUCTION) {
    if (!BuildConfig.IS_PRODUCTION) {
      doNested();
    }
    afterCode();
  }
}

void case7_2() {
  if (BuildConfig.IS_PRODUCTION) {
    doA();
  } else {
    if (BuildConfig.IS_PRODUCTION) {
      doB();
    }
    doC();
  }
}

// ============================================================
// Group 8: Edge cases and safety
// ============================================================

void case8_1() { var s = "if (true) { do something }"; }

void case8_2() {
  // if (BuildConfig.IS_PRODUCTION) {
  //   doSomething();
  // }
  doActual();
}

void case8_3() { var a = true; var b = false; }

// ============================================================
// Group 9: else if (true/false)
// ============================================================

void case9_1() {
  if (signUpType == "cosmos") {
    doComplex();
  } else if (BuildConfig.IS_PRODUCTION) {
    toEarlyUid();
  } else {
    toSignUp();
  }
}

void case9_2() {
  if (someCondition()) {
    doA();
  } else if (!BuildConfig.IS_PRODUCTION) {
    doB();
  } else {
    doC();
  }
}
