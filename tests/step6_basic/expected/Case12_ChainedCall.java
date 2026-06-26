package com.test;

public class Case12_ChainedCall {

    // Case 12.2: 独立调用有分号 → 应删
    // Case 12.3: 链式调用无分号 → 不应删
    private Observable showStatus() {
        return Observable.empty();
    }

    public void caller() {
        showStatus()
            .subscribe();
    }
}
