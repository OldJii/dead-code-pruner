// ============================================================
// Group 1: Constant folding
// ============================================================

void case1_1() {
  doIntl();
}

void case1_2() {
}

bool case1_3() {
  return true;
}

void case1_4() {
  var s = "intl";
  print(s);
}

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

void case2_1() {
}

void case2_2() {
  if (alive()) {
    doSomething();
  }
}

void case2_3() {
}

void case2_4() {
  if (alive()) {
    doSomething();
  }
}

// ============================================================
// Group 3: Compound boolean + ternary
// ============================================================

void case3_1() {
  var x = "intl";
  print(x);
}

void case3_2() {
  var x = "intl";
  print(x);
}

// ============================================================
// Group 4: if(false) block removal
// ============================================================

void case4_1() {
  afterCode();
}

void case4_2() {
}

void case4_3() {
  alive();
}

void case4_4() {
  if (condition) {
    doSomething();
  }
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

void case5_1() {
  doSomething();
}

void case5_2() {
  doA();
  doB();
}

void case5_3() {
  doIntl();
}

// ============================================================
// Group 6: Dead code removal after exit
// ============================================================

bool case6_1() {
  if (isGranted()) { return true; }
  return true;
}

void case6_2() {
  doFirst();
  return;
}

// ============================================================
// Group 7: Nested and complex
// ============================================================

void case7_1() {
  afterCode();
}

void case7_2() {
  doA();
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
  } else {
    toEarlyUid();
  }
}

void case9_2() {
  if (someCondition()) {
    doA();
  } else {
    doC();
  }
}
