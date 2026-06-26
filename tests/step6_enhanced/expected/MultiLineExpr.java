public class MultiLineExpr {

  public void testMultiLineAssignment() {
    boolean result =
        false;
    doSomething(result);
  }

  public void testStandaloneCall() {
    doSomething(true);
  }

  public void testIfCondition() {
    if (false) {
      doSomething(true);
    }
  }

  public void testInlineInCondition() {
    if (false) {
      doSomething(true);
    }
  }

  private void doSomething(boolean b) {}
}
