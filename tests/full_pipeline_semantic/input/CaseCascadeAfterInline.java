class CaseCascadeAfterInline {
    private boolean disabled() { return false; }
    private static boolean enabled() { return true; }

    void render() {
        if (disabled()) {
            dead();
        }
        after();
    }

    void renderStatic() {
        if (CaseCascadeAfterInline.enabled()) {
            live();
        }
    }
}
