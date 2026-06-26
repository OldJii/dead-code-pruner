public class SecondPassDead {

  // 场景1：void方法调用了dead boolean方法，dead被内联后if(false)被清理，方法变成只有return;
  private boolean isFeatureEnabled() {
    return false;
  }

  private void startFeature() {
    if (!isFeatureEnabled()) {
      return;
    }
    doHeavyWork();
    doMoreWork();
  }

  // 场景2：boolean方法调用了dead boolean方法，内联后变成只返回常量
  private boolean checkCurFew() {
    if (!isFeatureEnabled()) {
      return false;
    }
    return performCheck();
  }

  // 场景3：方法体被清理后只剩空壳
  private void checkForeground() {
    if (isFeatureEnabled() && isActive()) {
      doRedirect();
      finish();
    }
  }

  // 场景4：方法调用链 - A调用B，B是dead的，A内联后也变dead
  private boolean isEnabled() {
    return false;
  }

  private boolean shouldShow() {
    return isEnabled();
  }

  public void render() {
    if (shouldShow()) {
      showUI();
    }
    renderOther();
  }

  // 保留的方法
  private boolean performCheck() { return true; }
  private boolean isActive() { return true; }
  private void doHeavyWork() {}
  private void doMoreWork() {}
  private void doRedirect() {}
  private void finish() {}
  private void showUI() {}
  private void renderOther() {}
}
