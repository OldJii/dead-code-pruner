package com.test;

/**
 * 接口：默认实现
 * 测试点：接口默认返回值不应被清理
 */
public interface ICallback {

  default boolean onEvent() {
    return false;
  }

  default void onDismiss() {
  }
}
