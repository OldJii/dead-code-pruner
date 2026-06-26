package com.test;

/**
 * 父类：有子类 ChildOverrideSame 和 ChildOverrideDiff
 * 测试点：父类方法的处理取决于子类 Override 情况
 */
public class ParentClass {

  // 所有子类 Override 都返回 false → 整条链可内联
  public boolean parentMethod() {
    return false;
  }

  // 所有子类 Override 都为空 → 整条链调用可删除
  public void parentVoid() {
  }

  // 子类 Override 返回不同值 → 不能内联
  public boolean parentDiffMethod() {
    return false;
  }

  // 没有子类 Override → 但因为有子类存在，应视情况决定
  public boolean noOverrideMethod() {
    return true;
  }

  // 有实际逻辑，不是死方法
  public boolean hasLogic() {
    return System.currentTimeMillis() > 0;
  }
}
