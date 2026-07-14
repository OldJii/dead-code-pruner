public class BooleanEdgeCases {

  private boolean deadMethod() {
    return false;
  }

  // 场景1：(false) || expr → expr
  public boolean testParenFalseOr() {
    return (deadMethod()) || otherCheck();
  }

  // 场景2：expr || (false) → expr
  public boolean testOrParenFalse() {
    return otherCheck() || (deadMethod());
  }

  // 场景3：false + "" → "false"
  public void testFalsePlusEmpty() {
    jsonObject.put("key", deadMethod() + "");
  }

  // 场景4：else if (false) { } 应整块删除
  public void testElseIfFalse() {
    if (someCondition()) {
      doA();
    } else if (deadMethod()) {
      doB();
    } else {
      doC();
    }
  }

  // 场景5：if (false) { } else if (real) { } → if (real) { }
  public void testIfFalseElseIf() {
    if (deadMethod()) {
      doA();
    } else if (someCondition()) {
      doB();
    } else {
      doC();
    }
  }

  // 场景6：三元表达式 false ? x : y → y
  public void testTernaryFalse() {
    int val = deadMethod() ? 0.1f : 0.15f;
    setMargin(val);
  }

  // 保留的方法
  private boolean otherCheck() { return true; }
  private boolean someCondition() { return true; }
  private Object jsonObject;
  private void doA() {}
  private void doB() {}
  private void doC() {}
  private void setMargin(float v) {}
}
