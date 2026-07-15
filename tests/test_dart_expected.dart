// ============================================================
// Group 1: Constant folding
// ============================================================

void case1_1() {
  doPrimary();
}

void case1_2() {
}

bool case1_3() {
  return true;
}

void case1_4() {
  var s = "primary";
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
  var x = "primary";
  print(x);
}

void case3_2() {
  var x = "primary";
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
  doPrimary();
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
  if (flowMode == "special") {
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

// ============================================================
// Group 10: Compound boolean expansions
// ============================================================

void case10_1() { if (someCondition()) { doSomething(); } }
void case10_2() { var b = isChinese(); }
void case10_3() { if (someCondition()) { doSomething(); } }
void case10_4() { var b = someCondition(); }
void case10_5() { var s = "primary"; }

// ============================================================
// Group 11: Unreachable after return
// ============================================================

void case11_1() {
  setup();
  return;
}

bool case11_2() {
  return true;
}

// ============================================================
// Group 12: Multi-line assignment safety
// ============================================================

void case12_1(bool flag) {
  bool isOneWay =
      false;
  use(isOneWay);
}

// ============================================================
// Group 13: Local constant propagation
// ============================================================

void case13_1() {
  doPrimary();
}

void case13_2() {
  final result = "primary";
  print(result);
}

// ============================================================
// Group 14: Nested ternary
// ============================================================

int case14_1(int x) {
  return (x > 0 ? 1 : 2);
}

// ============================================================
// Group 15: else-if chains
// ============================================================

void case15_1(int x) {
  if (x > 0) {
    doPositive();
  } else {
    doNegative();
  }
}
