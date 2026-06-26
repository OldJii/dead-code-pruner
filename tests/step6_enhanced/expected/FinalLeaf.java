package com.test;

/**
 * final 类：不可能有子类
 * 测试点：final 类中的 public 方法应被视同 private
 */
public final class FinalLeaf {

  public boolean isActive() {
    return false;
  }

  public void cleanup() {
  }

  public void doStuff() {
    if (isActive()) {
      System.out.println("active");
    }
    cleanup();
  }
}
