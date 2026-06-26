// Rust test cases for dead-code-pruner

// ============================================================
// Group 1: Constant replacement
// ============================================================

fn case1_1() {
    do_intl();
}

fn case1_2() {
    after_code();
}

fn case1_3() {
    do_intl();
}

fn case1_6() -> bool { return true; }

fn case1_7() { let is_intl = true; do_something(is_intl); }

fn case1_8() { foo(true, "test"); }

// ============================================================
// Group 2: Simple boolean operations
// ============================================================

fn case2_1() { }

fn case2_2() { alive(); }

fn case2_3() { }

fn case2_4() { alive(); }

// ============================================================
// Group 3: Compound boolean
// ============================================================

fn case3_1() {
}

fn case3_2() { let b = false; }

fn case3_3() { do_something(); }

fn case3_4() { let b = true; }

fn case3_7() {
}

fn case3_9() { force_calc = force_calc; }

// ============================================================
// Group 4: if(false) block removal
// ============================================================

fn case4_1() {
    after_code();
}

fn case4_2() {
}

fn case4_3() {
    alive();
}

fn case4_4() {
    if condition {
        do_something();
    }
}

// ============================================================
// Group 5: if(true) block simplification
// ============================================================

fn case5_1() {
    do_something();
}

fn case5_2() {
    do_a();
    do_b();
}

fn case5_3() {
    do_intl();
}

// ============================================================
// Group 6: Dead code removal
// ============================================================

fn case6_1() -> bool {
    if is_granted() { return true; }
    return true;
}

fn case6_2() {
    do_first();
    return;
}

// ============================================================
// Group 7: Single-line if(false) return
// ============================================================

fn case7_1() -> i32 {
    let result = do_work();
    return result;
}

// ============================================================
// Group 9: Nested and complex
// ============================================================

fn case9_1() {
    after_code();
}

fn case9_2() {
    do_b();
    after_code();
}

fn case9_9() {
    do_deep();
    after_code();
}

fn case9_13() {
    alive();
}

// ============================================================
// Group 10: Edge cases
// ============================================================

fn case10_1() { let s = "if true { do something }"; }

fn case10_4() { a = true; b = false; }

fn case10_7() -> bool { return true; }
fn case10_7b() -> bool { return false; }

fn case10_9() { set_enabled(true); set_visible(false); }

// ============================================================
// Group 11: else if (true/false)
// ============================================================

fn case11_1() {
    if sign_up_type == "cosmos" {
        do_complex();
    } else {
        to_early_uid();
    }
}

fn case11_2() {
    if sign_up_type == "cosmos" {
        do_complex();
    } else {
        to_sign_up();
    }
}

fn case11_4() {
    if some_condition() {
        do_a();
    }
    after_code();
}

// ============================================================
// Group 12: Parenthesized boolean in && ||
// ============================================================

fn case12_1() {
    if not_null(data) {
        process(data);
    }
}

fn case12_2() {
    let ok = check();
}

fn case12_3() {
}

// ============================================================
// Group 13: Cross-line boolean
// ============================================================

fn case13_1() {
    if some_condition() {
        do_something();
    }
}

fn case13_3() {
}

fn case13_4() {
    if some_condition() {
        do_something();
    }
}

// ============================================================
// Group 15-16: Comparison + boolean safety
// ============================================================

fn case15_1() {
}

fn case15_7() {
    do_intl();
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
    return;
}

fn case17_6() {
    return;
}

fn case17_7() {
    do_something();
}

// ============================================================
// Group 18: } boundary
// ============================================================

fn case18_1() -> bool {
    if debug_build && debug_flag {
        return true;
    }
    return false;
}

// ============================================================
// Group 19: if(true){return}else{...}
// ============================================================

fn case19_3() {
    do_intl();
    do_common();
}

// ============================================================
// Group 20: Single-line if else
// ============================================================

fn case20_1() {
    to_pwd();
}

fn case20_2() {
    do_intl();
}

// ============================================================
// Group 23: match boundary
// ============================================================

fn case23_1(privilege: i32) -> String {
    match privilege {
        1 => {
            return build_intl(privilege);
        }
        2 => return build_undo(privilege),
        _ => return build_default(privilege),
    }
}
