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
  }

  public void testInlineInCondition() {
  }

  private void doSomething(boolean b) {}
}
