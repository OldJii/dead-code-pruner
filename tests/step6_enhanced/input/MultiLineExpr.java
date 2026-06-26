public class MultiLineExpr {

  private boolean isCertQ4() {
    return false;
  }

  public void testMultiLineAssignment() {
    boolean result =
        isCertQ4()
            && someCondition()
            && anotherCondition();
    doSomething(result);
  }

  public void testStandaloneCall() {
    isCertQ4();
    doSomething(true);
  }

  public void testIfCondition() {
    if (isCertQ4()) {
      doSomething(true);
    }
  }

  public void testInlineInCondition() {
    if (isCertQ4()
        && someCondition()) {
      doSomething(true);
    }
  }

  private boolean someCondition() { return true; }
  private boolean anotherCondition() { return true; }
  private void doSomething(boolean b) {}
}
