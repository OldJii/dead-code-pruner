package com.test;

/**
 * 抽象基类：框架扩展点
 * 测试点：Abs/Base 前缀的类中的方法应跳过
 */
public abstract class AbstractBase {

  public boolean shouldBlock() {
    return false;
  }

  public void onInit() {
  }
}
