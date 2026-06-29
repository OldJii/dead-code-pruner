package com.test;

/**
 * 叶子类（无子类），包含多个无意义 public 方法
 * 测试点：叶子类 public 方法应被视同 private 处理
 */
public class LeafHelper {

  // 应删除：void 空方法，无调用者
  public void doNothing() {
  }

  // 应删除：boolean 返回常量，无调用者
  public boolean isEnabled() {
    return false;
  }

  // 应保留：boolean 返回常量，但被 CallerFile 调用 → 内联为 false
  public boolean isFeatureOn() {
    return false;
  }

  // 应保留：void 空方法，但被 CallerFile 调用 → 调用语句应删除
  public void reset() {
  }

  // 应保留：有实际逻辑
  public boolean hasData() {
    return list != null && list.size() > 0;
  }

  private Object list;

  public void doWork() {
    if (isFeatureOn()) {
      System.out.println("feature on");
    }
    reset();
    System.out.println("old flag");
  }
}
