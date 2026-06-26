public class BooleanEdgeCases {

  // 场景1：(false) || expr → expr
  public boolean testParenFalseOr() {
    return true;
  }

  // 场景2：expr || (false) → expr
  public boolean testOrParenFalse() {
    return true;
  }

  // 场景3：false + "" → "false"
  public void testFalsePlusEmpty() {
    jsonObject.put("key", "false");
  }

  // 场景4：else if (false) { } 应整块删除
  public void testElseIfFalse() {

  }

  // 场景5：if (false) { } else if (real) { } → if (real) { }
  public void testIfFalseElseIf() {

  }

  // 场景6：三元表达式 false ? x : y → y
  public void testTernaryFalse() {
    int val = 0.15f;
    setMargin(val);
  }

  private Object jsonObject;
  private void setMargin(float v) {}
}
