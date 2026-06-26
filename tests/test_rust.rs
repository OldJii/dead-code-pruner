// Rust test cases for dead-code-pruner

// ============================================================
// Group 1: Constant replacement
// ============================================================

fn case1_1() {
    if INTL_FLAG { do_intl(); }
}

fn case1_2() {
    if !INTL_FLAG { do_domestic(); }
    after_code();
}

fn case1_3() {
    if INTL_FLAG { do_intl(); } else { do_domestic(); }
}

fn case1_6() -> bool { return INTL_FLAG; }

fn case1_7() { let is_intl = INTL_FLAG; do_something(is_intl); }

fn case1_8() { foo(INTL_FLAG, "test"); }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

fn case2_1() { if !true { dead(); } }

fn case2_2() { if !false { alive(); } }

fn case2_3() { if true == false { dead(); } }

fn case2_4() { if true != false { alive(); } }

// ============================================================
// Group 3: Compound boolean
// ============================================================

fn case3_1() {
    if false && picks_guide_user { do_something(); }
}

fn case3_2() { let b = is_chinese() && false; }

fn case3_3() { if true || some_condition() { do_something(); } }

fn case3_4() { let b = some_condition() || true; }

fn case3_7() {
    if false && !is_empty(identifier) && contains(identifier, "guideNewUser") {
        do_something();
    }
}

fn case3_9() { force_calc = force_calc || false; }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

fn case4_1() {
    if false {
        do_something_dead();
    }
    after_code();
}

fn case4_2() {
    if false {
        dead_code1();
        dead_code2();
    }
}

fn case4_3() {
    if false {
        dead();
    } else {
        alive();
    }
}

fn case4_4() {
    if false {
        dead();
    } else if condition {
        do_something();
    }
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

fn case5_1() {
    if true {
        do_something();
    }
}

fn case5_2() {
    if true {
        do_a();
        do_b();
    }
}

fn case5_3() {
    if true {
        do_intl();
    } else {
        do_domestic();
    }
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

fn case6_1() -> bool {
    if is_granted() { return true; }
    if true { return true; }
    after_code();
    return false;
}

fn case6_2() {
    do_first();
    if true { return; }
    do_second();
    do_third();
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

fn case7_1() -> i32 {
    if false { return -1; }
    let result = do_work();
    return result;
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

fn case9_1() {
    if false {
        if inner { do_inner(); }
    }
    after_code();
}

fn case9_2() {
    if false { do_a(); }
    if true { do_b(); }
    after_code();
}

fn case9_9() {
    if true {
        if true { do_deep(); }
    }
    after_code();
}

fn case9_13() {
    if false { dead1(); }
    if false { dead2(); }
    if false { dead3(); }
    alive();
}

// ============================================================
// Group 10: Edge cases
// ============================================================

fn case10_1() { let s = "if true { do something }"; }

fn case10_4() { a = !false; b = !true; }

fn case10_7() -> bool { return true; }
fn case10_7b() -> bool { return false; }

fn case10_9() { set_enabled(true); set_visible(false); }

// ============================================================
// Group 11: else if (true/false)
// ============================================================

fn case11_1() {
    if sign_up_type == "cosmos" {
        do_complex();
    } else if true {
        to_early_uid();
    } else {
        to_sign_up();
    }
}

fn case11_2() {
    if sign_up_type == "cosmos" {
        do_complex();
    } else if false {
        do_dead();
    } else {
        to_sign_up();
    }
}

fn case11_4() {
    if some_condition() {
        do_a();
    } else if false {
        do_dead();
    }
    after_code();
}

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

fn case12_1() {
    if not_null(data) && (true) {
        process(data);
    }
}

fn case12_2() {
    let ok = check() || (false);
}

fn case12_3() {
    if (false) && some_check() {
        dead();
    }
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

fn case13_1() {
    if true
        && some_condition() {
        do_something();
    }
}

fn case13_3() {
    if false
        && some_condition()
        && another_condition() {
        do_something();
    }
}

fn case13_4() {
    if some_condition() &&
        true {
        do_something();
    }
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

fn case15_1() {
    if position == 0 && !INTL_FLAG {
        do_something();
    }
}

fn case15_7() {
    if position == 0 || INTL_FLAG {
        do_intl();
    }
}

fn case16_1() {
    if local_lock == true && remote_lock == false {
        do_something();
    }
}

// ============================================================
// Group 17: Dead code after return
// ============================================================

fn case17_2() {
    setup();
    if INTL_FLAG { return; }
    do_something_a();
    do_something_b();
}

fn case17_6() {
    if INTL_FLAG { return; }
}

fn case17_7() {
    if !INTL_FLAG { return; }
    do_something();
}

// ============================================================
// Group 18: } boundary
// ============================================================

fn case18_1() -> bool {
    if debug_build && debug_flag {
        return true;
    }
    return is_ready() && !INTL_FLAG;
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

fn case19_3() {
    if INTL_FLAG {
        do_intl();
    } else {
        do_local();
    }
    do_common();
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

fn case20_1() {
    if INTL_FLAG { to_pwd(); }
    else { login_strategy(); }
}

fn case20_2() {
    if !INTL_FLAG { do_local(); }
    else { do_intl(); }
}

// ============================================================
// Group 23: match boundary
// ============================================================

fn case23_1(privilege: i32) -> String {
    match privilege {
        1 => {
            if INTL_FLAG {
                return build_intl(privilege);
            }
            return build_local(privilege);
        }
        2 => return build_undo(privilege),
        _ => return build_default(privilege),
    }
}
