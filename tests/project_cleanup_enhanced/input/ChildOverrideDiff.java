package com.test;

/**
 * 子类2：Override 返回与父类不同的常量
 * 测试点：parentDiffMethod 不应被内联（Override 链不一致）
 */
public class ChildOverrideDiff extends ParentClass {

  @Override
  public boolean parentDiffMethod() {
    return true;
  }
}
