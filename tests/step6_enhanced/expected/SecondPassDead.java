public class SecondPassDead {

  private void startFeature() {
    return;
  }

  // 场景2：boolean方法调用了dead boolean方法，内联后变成只返回常量
  private boolean checkCurFew() {
    return false;
  }

  // 场景3：方法体被清理后只剩空壳
  private void checkForeground() {
  }

  private boolean shouldShow() {
    return false;
  }

  public void render() {
    if (shouldShow()) {
    }
  }

}
