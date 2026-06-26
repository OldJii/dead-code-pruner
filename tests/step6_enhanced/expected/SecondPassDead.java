public class SecondPassDead {

  private void startFeature() {
    if (true) {
      return;
    }
  }

  // 场景2：boolean方法调用了dead boolean方法，内联后变成只返回常量
  private boolean checkCurFew() {
    if (true) {
      return false;
    }
    return true;
  }

  // 场景3：方法体被清理后只剩空壳
  private void checkForeground() {
    if (false) {
    }
  }

  private boolean shouldShow() {
    return false;
  }

  public void render() {
    if (shouldShow()) {
    }
  }

}
