package com.test;

import com.p1.mobile.putong.common.BuildConfig;
import com.p1.mobile.putong.core.member.BuildConfig;

public class TestAllCases {

  // ============================================================
  // 第一组：常量替换
  // ============================================================

  void case1_1() {
    if (BuildConfig.IS_PRODUCTION) { doIntl(); }
  }

  void case1_2() {
    if (!BuildConfig.IS_PRODUCTION) { doDomestic(); }
    afterCode();
  }

  void case1_3() {
    if (com.example.BuildConfig.IS_PRODUCTION
        && act instanceof FakeLikersAct) {
      showFrom = "intl";
    }
  }

  void case1_4() {
    // if (BuildConfig.IS_PRODUCTION) { ... }
    /* BuildConfig.IS_PRODUCTION check */
  }

  void case1_5() {
    String s = "BuildConfig.IS_PRODUCTION is true";
  }

  boolean case1_6() { return BuildConfig.IS_PRODUCTION; }

  void case1_7() { boolean isIntl = BuildConfig.IS_PRODUCTION; doSomething(isIntl); }

  void case1_8() { foo(BuildConfig.IS_PRODUCTION, "test"); }

  // ============================================================
  // 第二组：简单布尔运算
  // ============================================================

  void case2_1() { if (!true) { dead(); } }

  void case2_2() { if (!false) { alive(); } }

  void case2_3() { if (true == false) { dead(); } }

  void case2_4() { if (true != false) { alive(); } }

  void case2_5() { if (false == false) { alive(); } }

  // Case 2.6: (true) → true （去括号）
  void case2_6() {
    if (NullChecker.notNull(rememberdLogin)
          && (true)) {
      authData.put(rememberdLogin.auth);
      return Observable.just(Unit.UNIT);
    }
  }

  // Case 2.7: (false) → false（去括号）
  void case2_7() {
    boolean b = isSomething() && (false);
  }

  // Case 2.8: 嵌套括号 ((true)) — 多轮收敛处理
  void case2_8() {
    if (((true))) {
      doSomething();
    }
  }

  // ============================================================
  // 第三组：复合布尔模式
  // ============================================================

  void case3_1() {
    if (false && paramsHolder.cardData.getUserInfo().picksGuideUser) { doSomething(); }
  }

  void case3_2() { boolean b = isChinese() && false; }

  void case3_3() { if (true || someCondition()) { doSomething(); } }

  void case3_4() { boolean b = someCondition() || true; }

  void case3_5() { int val = countDownTimes % (false ? 2 : 4); }

  void case3_6() { String s = true ? "intl" : "local"; }

  void case3_7() {
    if (false
        && !TextUtils.isEmpty(identifier)
        && identifier.contains("guideNewUserCompleteMaterial")) {
      doSomething();
    }
  }

  void case3_8() {
    // if (false && someCondition()) { return; }
  }

  void case3_9() { forceCalc = forceCalc || false; }

  void case3_10() { if (true && someCondition()) { doSomething(); } }

  void case3_11() { boolean b = isChinese() && true; }

  void case3_12() { if (false || someCondition()) { doSomething(); } }

  // ============================================================
  // 第四组：if(false) 块删除
  // ============================================================

  void case4_1() {
    if (false) { deadCode(); }
    afterCode();
  }

  void case4_2() {
    if (false) { deadCode(); } else { doElse(); }
  }

  void case4_3() {
    if (false) {
      deadCode();
    } else if (someCondition()) {
      doB();
    } else {
      doC();
    }
    afterCode();
  }

  void case4_4() {
    if (false) { deadCode(); } else if (someCondition()) { doB(); }
    afterCode();
  }

  // ============================================================
  // 第五组：if(true) 块简化
  // ============================================================

  void case5_1() {
    if (true) { doA(); }
    afterCode();
  }

  void case5_2() {
    if (true) { doA(); } else { doB(); }
    afterCode();
  }

  void case5_3() {
    if (true) { doA(); } else if (someCondition()) { doB(); }
    afterCode();
  }

  void case5_4() {
    if (true) {
      doA();
    } else if (someCondition()) {
      doB();
    } else {
      doC();
    }
    afterCode();
  }

  void case5_5() {
    if (true) {
    } else {
      doB();
    }
    afterCode();
  }

  // ============================================================
  // 第六组：死代码删除
  // ============================================================

  protected boolean case6_1() {
    if (GrantedPermissionHelper.isReadPhoneStateGranted()) { return true; }
    if (true) { return true; }
    return PermissionHelper.isAllPermissionGranted(PermissionHelper.REQUIRED_PERMISSIONS);
  }

  void case6_2() {
    doFirst();
    if (true) { return; }
    doSecond();
    doThird();
    if (someCondition()) { doFourth(); }
  }

  void case6_3() {
    if (true) { throw new RuntimeException("error"); }
    cleanup();
  }

  void case6_4() {
    if (true) { if (check) { return; } }
    afterCode();
  }

  void case6_5() {
    for (int i = 0; i < 10; i++) {
      if (true) { break; }
      processItem(i);
    }
  }

  void case6_6() {
    doFirst();
    if (true) { return; }
  }

  // ============================================================
  // 第七组：单行 if(false) return
  // ============================================================

  int case7_1() {
    if (false) return -1;
    try { return doWork(); } catch (Exception e) { return 0; }
  }

  Object case7_2() {
    if (false) return null;
    try { return getData(); } catch (Exception e) { return null; }
  }

  boolean case7_3() {
    if (false) return false;
    if (url.startsWith("sms:")) { return true; }
    return false;
  }

  // ============================================================
  // 第八组：Kotlin if 表达式
  // ============================================================

  void case8_1() {
    selectedIdx = false ? 0 : selectedIdx;
    selectedIdx = selectedIdx.coerceAtLeast(0);
  }

  // ============================================================
  // 第九组：嵌套和复杂场景
  // ============================================================

  void case9_1() {
    if (false) { if (true) { doA(); } doB(); }
    afterCode();
  }

  void case9_2() {
    if (false) { doA(); }
    if (true) { doB(); }
    afterCode();
  }

  void case9_3() {
    if (someCondition()) {
      doA();
    } else {
      if (true) { doB_intl(); } else { doB_domestic(); }
    }
  }

  void case9_4() { foo(false ? 2 : 4, true ? "intl" : "local"); }

  void case9_5() {
    forceCalculation =
        forceCalculation || countDownTimes % (false ? 2 : 4) == 0;
  }

  void case9_6() { args(context, !true, "value"); }

  void case9_7() { args(context, !true || IntlDeviceController.isPhotoCut()); }

  void case9_8() { if (true && checkPermission()) { grant(); } }

  void case9_9() {
    if (true) { if (true) { doDeep(); } }
    afterCode();
  }

  void case9_10() {
    try { if (false) { doA(); } doB(); } catch (Exception e) { handleError(e); }
  }

  void case9_11() {
    for (int i = 0; i < 10; i++) { if (true) { process(i); } }
  }

  void case9_12() {
    if (someCondition()) { doA(); } else { if (false) { doDead(); } doB(); }
  }

  void case9_13() {
    if (false) { dead1(); }
    if (false) { dead2(); }
    if (false) { dead3(); }
    alive();
  }

  // ============================================================
  // 第十组：边界和安全保护
  // ============================================================

  void case10_1() { String s = "if (true) { do something }"; }

  void case10_2() {
    // if (true) {
    //   doSomething();
    // } else {
    //   doOther();
    // }
    doActual();
  }

  void case10_3() {
    boolean streamEndWasReached; // if (true) then _streamPos shows real end
    setTrue(false); setFalse(true);
  }

  void case10_4() { a = !false; b = !true; }

  void case10_5() {
    while (true) { if (shouldStop()) break; doWork(); }
  }

  void case10_6() {
    // do { } while (false); // 这行是注释不应处理
    int x = 1;
  }

  boolean case10_7() { return true; }
  boolean case10_7b() { return false; }

  void case10_8() {
    boolean enabled = true; boolean disabled = false; setConfig(enabled, disabled);
  }

  void case10_9() { setEnabled(true); setVisible(false); }

  void case10_10() { String s = "he said \"true\" about BuildConfig.IS_PRODUCTION"; }

  void case10_11() { String s = "value is " + true + " now"; }

  void case10_12() { int x = arr[true ? 0 : 1]; }

  void case10_13() { @SuppressWarnings("unchecked") boolean x = true; }

  void case10_14() {
    button.setOnClickListener(new View.OnClickListener() {
      @Override public void onClick(View v) { if (true) { doAction(); } }
    });
  }

  void case10_15() { if ((true && (a > b)) || (c < d)) { doSomething(); } }

  void case10_16() { if (false) { doNothing(); } }

  // ============================================================
  // 第十一组：else if (true/false) 场景 [NEW!]
  // ============================================================

  // Case 11.1: if (X) { ... } else if (true) { A } else { B } → if (X) { ... } else { A }
  void case11_1() {
    if (signUpData.signUpType == SignUpType.cosmos) {
      viewModel.doSomethingComplex();
    } else if (true) {
      toEarlyUidSignUp();
    } else {
      toSignUp(null);
    }
  }

  // Case 11.2: if (X) { ... } else if (false) { A } else { B } → if (X) { ... } else { B }
  void case11_2() {
    if (signUpData.signUpType == SignUpType.cosmos) {
      viewModel.doSomethingComplex();
    } else if (false) {
      doDead();
    } else {
      toSignUp(null);
    }
  }

  // Case 11.3: if (X) { ... } else if (true) { A } → if (X) { ... } else { A }
  void case11_3() {
    if (someCondition()) {
      doA();
    } else if (true) {
      doB();
    }
  }

  // Case 11.4: if (X) { ... } else if (false) { A } → if (X) { ... }
  void case11_4() {
    if (someCondition()) {
      doA();
    } else if (false) {
      doDead();
    }
    afterCode();
  }

  // Case 11.5: if (X) { ... } else if (false) { A } else if (Y) { B } else { C }
  // → if (X) { ... } else if (Y) { B } else { C }
  void case11_5() {
    if (someCondition()) {
      doA();
    } else if (false) {
      doDead();
    } else if (otherCondition()) {
      doB();
    } else {
      doC();
    }
    afterCode();
  }

  // Case 11.6: 带有复杂体的 else if (true)
  private Action0 case11_6 =
      () -> {
        isSigning = true;
        SignUpData signUpData = getSignUpData();
        if (signUpData.signUpType == SignUpType.cosmos) {
          viewModel
              .act()
              .duringCreated(
                  ChinaMobileController.getInstance().queryCertificationInfo(5000), false)
              .subscribe(
                  Rxu.ob(
                      info -> {
                        if (info.failed) {
                          isSigning = false;
                          viewModel.act().progressDismiss();
                          Toast.messageThrottle(R.string.ERROR_NETWORK);
                        } else {
                          setSignUpToken(info.token, info.openId);
                          toSignUp(info.grantType);
                        }
                      }));
        } else if (true) {
          toEarlyUidSignUp();
        } else {
          toSignUp(null);
        }
      };

  // Case 11.7: else if (true) 后有 return 导致死代码
  int case11_7() {
    if (condA()) {
      return 1;
    } else if (true) {
      return 2;
    } else {
      return 3;
    }
  }

  // ============================================================
  // 第十二组：&& (true/false) 带括号布尔 [NEW!]
  // ============================================================

  // Case 12.1: && (true)
  void case12_1() {
    if (NullChecker.notNull(data)
          && (true)) {
      process(data);
    }
  }

  // Case 12.2: || (false)
  void case12_2() {
    boolean ok = check() || (false);
  }

  // Case 12.3: (false) && expr
  void case12_3() {
    if ((false) && someCheck()) {
      dead();
    }
  }

  // Case 12.4: (true) || expr
  void case12_4() {
    boolean ok = (true) || someCondition();
  }

  // ============================================================
  // 第十三组：跨行布尔表达式 [NEW!]
  // ============================================================

  // Case 13.1: true && expr 跨行
  void case13_1() {
    if (true
        && TEnum.equals(nextStage, StepSignupStage.ethnicity_saved)) {
      intent = SignUpIntlEthnicityLanguageAct.Companion.args(act, false);
    }
  }

  // Case 13.2: true || expr 跨行
  void case13_2() {
    if (true
        || !CoreProductController.isConversationOpExp()
        || (!Vu.visible(_unread_text_root) && !Vu.visible(_new_state_red_dot))) {
      return;
    }
  }

  // Case 13.3: false && expr 跨行
  void case13_3() {
    if (false
        && someCondition()
        && anotherCondition()) {
      doSomething();
    }
  }

  // Case 13.4: expr && true 跨行（&& 在行尾）
  void case13_4() {
    if (someCondition() &&
        true) {
      doSomething();
    }
  }

  // Case 13.5: expr || false 跨行
  void case13_5() {
    boolean b = someCondition()
        || false;
  }

  // Case 13.6: 复杂多行 else if + true &&
  void case13_6() {
    if (TEnum.equals(nextStage, StepSignupStage.picture_saved)) {
      intent = SignUpProfileImageAct.args(act);
    } else if (true
        && TEnum.equals(nextStage, StepSignupStage.ethnicity_saved)) {
      intent = SignUpIntlEthnicityLanguageAct.Companion.args(act, false);
    } else if (true
        && TEnum.equals(nextStage, StepSignupStage.language_saved)) {
      intent = SignUpIntlEthnicityLanguageAct.Companion.args(act, true);
    } else {
      intent = SignUpDetailsNewAct.args(act);
    }
  }

  // Case 13.7: false || expr 跨行
  void case13_7() {
    if (false
        || someCondition()) {
      doSomething();
    }
  }

  // ============================================================
  // 第十四组：跨行三元运算符 [NEW!]
  // ============================================================

  // Case 14.1: true ? X : Y 跨行（用户真实场景）
  void case14_1() {
    MediaLoaderCallbacks cb =
        true
            ? new MediaLoaderCallbacks(act(), true, false, true, 200)
            : new MediaLoaderCallbacks(act(), true, false, false, 100);
  }

  // Case 14.2: false ? X : Y 跨行
  void case14_2() {
    String label =
        false
            ? core.suggested
            : core.recommended;
  }

  // Case 14.3: true ? 多行表达式 : Y
  void case14_3() {
    int color =
        true
            ? act.getResources().getColor(R.color.core_color_99000000)
            : act.getResources().getColor(R.color.core_color_66000000);
  }

  // Case 14.4: false && expr 跨行 + 三行条件
  void case14_4() {
    if (false
        && !TextUtils.isEmpty(identifier)
        && identifier.contains("guideNewUser")) {
      doSomething();
    }
  }

  // Case 14.5: true || 多行 + 多个 ||
  void case14_5() {
    if (true
        || !CoreProductController.isEnabled()
        || (!Vu.visible(view1) && !Vu.visible(view2))) {
      return;
    }
    afterCode();
  }

  // ============================================================
  // 第十五组：比较运算符 + 赋值运算符 + 三元运算符边界 [NEW!]
  // find_expr_start_backward 必须正确区分 == != >= <= 和赋值 =
  // ============================================================

  // Case 15.1: position == 0 && false（compound expression）
  void case15_1() {
    if (position == 0 && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // Case 15.2: position != 0 && false
  void case15_2() {
    if (count != 0 && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // Case 15.3: value >= 5 && false
  void case15_3() {
    if (value >= 5 && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // Case 15.4: value <= 10 && false
  void case15_4() {
    if (value <= 10 && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // Case 15.5: 赋值 = 应该作为边界
  void case15_5() {
    boolean result = someCondition() && !BuildConfig.IS_PRODUCTION;
    use(result);
  }

  // Case 15.6: 复合赋值 += 也应该作为边界
  void case15_6() {
    flags += getFlags() && !BuildConfig.IS_PRODUCTION;
  }

  // Case 15.7: a == b || true 不能变成 a == true
  void case15_7() {
    if (position == 0 || BuildConfig.IS_PRODUCTION) {
      doIntl();
    }
  }

  // Case 15.8: a != b || true
  void case15_8() {
    if (type != TYPE_A || BuildConfig.IS_PRODUCTION) {
      doIntl();
    }
  }

  // Case 15.9: return a == b && false;
  void case15_9() {
    return position == 0 && !BuildConfig.IS_PRODUCTION;
  }

  // Case 15.10: 三元表达式中 EXPR && false（ternary 中 : 作为边界）
  void case15_10() {
    String s = condition ? getA() : getB() && !BuildConfig.IS_PRODUCTION;
  }

  // Case 15.11: 三元表达式中 EXPR && false（? 作为边界）
  void case15_11() {
    boolean ok = someCheck() ? getValue() && !BuildConfig.IS_PRODUCTION : defaultVal;
  }

  // Case 15.12: 多个比较混合 && false
  void case15_12() {
    if (a > 0 && b == 1 && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // Case 15.13: arr[i] == 0 && false（bracket + 比较 + &&）
  void case15_13() {
    if (arr[i] == 0 && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // Case 15.14: 方法调用返回值比较 && false
  void case15_14() {
    if (list.size() == 0 && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // Case 15.15: a == b && c == d && false（链式 && 全为 false）
  void case15_15() {
    if (a == 0 && b == 1 && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // Case 15.16: false && a == b（false && 比较表达式，find_expr_end_forward 必须越过 ==）
  void case15_16() {
    if (!BuildConfig.IS_PRODUCTION && position == 0) {
      doSomething();
    }
  }

  // Case 15.17: true || a != b（true || 比较表达式）
  void case15_17() {
    if (BuildConfig.IS_PRODUCTION || count != 0) {
      doIntl();
    }
  }

  // ============================================================
  // 第十六组：== true / == false 不应被错误简化 [NEW!]
  // true/false 作为比较操作数时，不应被 && || ? 规则匹配
  // ============================================================

  // Case 16.1: lock == true && lock == false（真实场景：CoreDbProvider）
  void case16_1() {
    if (local.lock == true
        && remote.lock == false) {
      doSomething();
    }
  }

  // Case 16.2: == false && expr（false 是比较操作数）
  void case16_2() {
    if (flag == false && someCondition()) {
      doSomething();
    }
  }

  // Case 16.3: expr && value == true（true 是比较操作数）
  void case16_3() {
    if (someCondition() && flag == true) {
      doSomething();
    }
  }

  // Case 16.4: expr && value != false（!= false 不应被匹配）
  void case16_4() {
    if (someCondition() && status != false) {
      doSomething();
    }
  }

  // Case 16.5: value == true || other（true 是比较操作数，不应被 true || 匹配）
  void case16_5() {
    if (flag == true || otherFlag) {
      doSomething();
    }
  }

  // Case 16.6: other || value == false（false 是比较操作数）
  void case16_6() {
    if (otherFlag || flag == false) {
      doSomething();
    }
  }

  // Case 16.7: value == false ? X : Y（false 是比较操作数，不应被 false ? 匹配）
  void case16_7() {
    String s = flag == false ? "yes" : "no";
  }

  // Case 16.8: value != true ? X : Y
  void case16_8() {
    String s = flag != true ? "yes" : "no";
  }

  // Case 16.9: return a == true && b == false;（两个比较操作数）
  void case16_9() {
    return lockA == true && lockB == false;
  }

  // Case 16.10: 混合场景：真正的 true/false + 比较中的 true/false
  void case16_10() {
    if (BuildConfig.IS_PRODUCTION && flag == true) {
      doSomething();
    }
  }

  // Case 16.11: 混合场景：比较中的 false + 真正的 && false
  void case16_11() {
    if (flag == false && !BuildConfig.IS_PRODUCTION) {
      doSomething();
    }
  }

  // ============================================================
  // 第十七组：单行 if(true) return/throw 后的死代码移除 [NEW!]
  // ============================================================

  // Case 17.1: constant if with early return clears dead code below
  private boolean case17_1(String text) {
    if (TextUtils.isEmpty(text)) return false;
    if (BuildConfig.IS_PRODUCTION) return false;
    if (!LocalUtil.isChineseCN()) return false;
    FoulWords data = Putong.foulWords.data_();
    if (data != null) {
      return Cu.find(data.badMood, e -> text.contains(e)) != null;
    } else {
      return false;
    }
  }

  // Case 17.2: if(true) return; 后续有多行代码
  void case17_2() {
    setup();
    if (BuildConfig.IS_PRODUCTION) return;
    doSomethingA();
    doSomethingB();
    doSomethingC();
  }

  // Case 17.3: if(true) throw 后续代码
  void case17_3() {
    if (BuildConfig.IS_PRODUCTION) throw new RuntimeException("not supported");
    doSomething();
    doSomethingElse();
  }

  // Case 17.4: 多个连续 if(true) return（只有第一个生效）
  void case17_4(int type) {
    if (type == 0) return;
    if (BuildConfig.IS_PRODUCTION) return;
    doSomething();
    if (BuildConfig.IS_PRODUCTION) return;
    doSomethingElse();
  }

  // Case 17.5: if(true) return 在 switch-case 或循环中（break/continue）
  void case17_5() {
    for (int i = 0; i < 10; i++) {
      if (BuildConfig.IS_PRODUCTION) continue;
      doSomething(i);
    }
  }

  // Case 17.6: if(true) return 后面紧跟 }（方法末尾，无死代码）
  void case17_6() {
    if (BuildConfig.IS_PRODUCTION) return;
  }

  // Case 17.7: if(false) 单行删除（确认不受影响）
  void case17_7() {
    if (!BuildConfig.IS_PRODUCTION) return;
    doSomething();
  }

  // ============================================================
  // 第十八组：} 边界问题 [NEW!]
  // find_expr_start_backward 不应穿过 } 进入前一个代码块
  // ============================================================

  // Case 18.1: if块之后的 return EXPR && false（真实场景：CoreProductController）
  static boolean case18_1() {
    if (Config.DEBUG_BUILD && core.user.debugFlag.get()) {
      return true;
    }
    return !"control".equals(ABManager.valueOfUserAb("feature"))
        && !BuildConfig.IS_PRODUCTION;
  }

  // Case 18.2: try-catch 后的 return EXPR && false
  static boolean case18_2() {
    try {
      init();
    } catch (Exception e) {
      log(e);
    }
    return isReady() && !BuildConfig.IS_PRODUCTION;
  }

  // Case 18.3: 多个 if 块后的 return
  static boolean case18_3() {
    if (conditionA()) {
      return true;
    }
    if (conditionB()) {
      return false;
    }
    return getResult() && !BuildConfig.IS_PRODUCTION;
  }

  // Case 18.4: for 循环后的 expr && false
  void case18_4() {
    for (int i = 0; i < 10; i++) {
      process(i);
    }
    boolean result = compute() && !BuildConfig.IS_PRODUCTION;
  }

  // ============================================================
  // 第十九组：if(true){return}else{...} 后的死代码 [NEW!]
  // ============================================================

  // Case 19.1: if(true){return A} else if(...){return B} 后有 fallback return
  static Object case19_1(int type) {
    if (BuildConfig.IS_PRODUCTION) {
      return new GPComponent(type);
    } else if (type == 1) {
      return new LocalComponent(type);
    }
    return new DefaultComponent(type);
  }

  // Case 19.2: if(true){多行return} 无 else（body_has_unconditional_exit 需追踪括号）
  private List<User> case19_2(String like) {
    if (BuildConfig.IS_PRODUCTION) {
      Map<String, Object> memoMap = getMemos();
      ArrayList<String> ids = Cu.map(memoMap.values(), m -> m.userId);
      return Putong.commonDbProvider.users.query(
          Filter.OR(
              User.NAME.CONTAINS(like),
              User.ID.IN(ids)),
          null,
          200);
    }
    return Putong.commonDbProvider.users.query(User.NAME.CONTAINS(like), null, 200);
  }

  // Case 19.3: if(true){不含return} else{...} 后有代码（不应删除）
  void case19_3() {
    if (BuildConfig.IS_PRODUCTION) {
      doIntl();
    } else {
      doLocal();
    }
    doCommon();
  }

  // ============================================================
  // 第二十组：单行 if(true/false) A; else B;（else 在下一行）
  // ============================================================

  // Case 20.1: if(true) A; else B;（保留 A，删除 else B）
  void case20_1() {
    if (BuildConfig.IS_PRODUCTION) toPwd();
    else loginStrategy();
  }

  // Case 20.2: if(false) A; else B;（删除 A，保留 B）
  void case20_2() {
    if (!BuildConfig.IS_PRODUCTION) doLocal();
    else doIntl();
  }

  // Case 20.3: if(true) return; else doSomething();（return 后死代码）
  void case20_3() {
    setup();
    if (BuildConfig.IS_PRODUCTION) return;
    else doLocal();
    doAfter();
  }

  // Case 20.4: if(false) return; else { block }（保留 block）
  void case20_4() {
    if (!BuildConfig.IS_PRODUCTION) return;
    else {
      doIntl();
      doMore();
    }
    doAfter();
  }

  // Case 20.5: if(false) A; else if (X) { B } else { C }
  void case20_5(int x) {
    if (!BuildConfig.IS_PRODUCTION) doLocal();
    else if (x > 0) {
      doPositive();
    } else {
      doNegative();
    }
  }

  // ============================================================
  // 第二十三组：switch/case 中的死代码边界
  // ============================================================

  // Case 22.5: 嵌套三元表达式 true ? (X ? A : B) : C
  int case22_5(int x) {
    return BuildConfig.IS_PRODUCTION
        ? x > 0
            ? R.string.A
            : R.string.B
        : R.string.C;
  }

  // Case 22.6: 嵌套三元表达式 false ? (X ? A : B) : C
  int case22_6(int x) {
    return !BuildConfig.IS_PRODUCTION
        ? x > 0
            ? R.string.A
            : R.string.B
        : R.string.C;
  }

  // Case 23.1: if(true){return} 在 switch/case 中不能越过 case 边界
  PrivilegeDescription case23_1(Privilege privilege) {
    switch (privilege) {
      case vip_super_like:
        if (BuildConfig.IS_PRODUCTION) {
          return buildIntl(privilege);
        }
        return buildLocal(privilege);
      case vip_undo:
        return buildUndo(privilege);
      default:
        return buildDefault(privilege);
    }
  }

  // Case 23.2: if(true){return} 在 switch/case 中 + else 块
  String case23_2(int type) {
    switch (type) {
      case 1:
        if (BuildConfig.IS_PRODUCTION) {
          return "intl";
        } else {
          return "local";
        }
      case 2:
        return "other";
    }
  }

  // ============================================================
  // 第二十四组：本地常量传播 (Step 1b)
  // ============================================================

  // Case 24.1: final boolean 本地变量传播
  void case24_1() {
    final boolean isProduction = BuildConfig.IS_PRODUCTION;
    if (isProduction) {
      doIntl();
    } else {
      doLocal();
    }
  }

  // Case 24.2: final boolean 传播后清理未使用声明
  void case24_2() {
    final boolean flag = BuildConfig.IS_PRODUCTION;
    String result = flag ? "intl" : "local";
    System.out.println(result);
  }

  // Case 24.3: 非 final 不应传播（可能被重新赋值）
  void case24_3() {
    boolean mutable = BuildConfig.IS_PRODUCTION;
    if (mutable) {
      doIntl();
    }
  }
}

// ============================================================
// Group 26: Java switch cases share declaration scope
// ============================================================

String case26_switchShared(int kind) {
  switch (kind) {
    case 1:
      if (BuildConfig.IS_PRODUCTION) {
        return "production";
      } else {
        logLocal();
      }
      String content = "local";
      return content;
    case 2:
      content = "later case";
      return content;
    default:
      return "default";
  }
}
