package test;

public class OuterClass {

  private static boolean outerFlag() {
    return false;
  }

  private static class InnerStatic {
    int x = 0;
    String name;

    InnerStatic(int x, String name) {
      this.x = x;
      this.name = name;
    }
  }

  private static boolean afterInner() {
    return true;
  }

  private void useFlags() {
    if (outerFlag()) {
      System.out.println("outer");
    }
    if (afterInner()) {
      System.out.println("after inner");
    }
  }

  private static class AnotherInner {
    private static boolean innerMethod() {
      return false;
    }
  }

  private static void afterAll() {
    AnotherInner.innerMethod();
  }
}
