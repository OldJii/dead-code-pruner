package com.test;

/**
 * 调用方文件：测试跨文件内联
 */
public class CallerFile {

  private LeafHelper helper = new LeafHelper();
  private ParentClass parent = new ChildOverrideSame();

  public void process() {
    // isFeatureOn() -> false → if(false) 应被后续 step2-4 简化
    if (helper.isFeatureOn()) {
      System.out.println("should be removed by cascade");
    }

    // reset() -> void 空方法 → 调用语句应删除
    helper.reset();

    // parentMethod() 在 ParentClass 返回 false，ChildOverrideSame 也返回 false
    // 所有 Override 链一致 → 应内联为 false
    if (parent.parentMethod()) {
      System.out.println("parent method");
    }

    // parentVoid() 在 ParentClass 为空，ChildOverrideSame 也为空
    parent.parentVoid();

    // 不应被影响的正常调用
    if (helper.hasData()) {
      System.out.println("has data");
    }
  }
}
