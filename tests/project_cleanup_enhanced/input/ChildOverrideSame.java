package com.test;

/**
 * 子类1：Override 返回与父类相同常量
 */
public class ChildOverrideSame extends ParentClass {

  @Override
  public boolean parentMethod() {
    return false;
  }

  @Override
  public void parentVoid() {
  }

  @Override
  public boolean parentDiffMethod() {
    return false;
  }
}
