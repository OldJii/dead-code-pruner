package test;

public class OuterClass {

  private static class InnerStatic {
    int x = 0;
    String name;

    InnerStatic(int x, String name) {
      this.x = x;
      this.name = name;
    }
  }

  private void useFlags() {
    if (false) {
      System.out.println("outer");
    }
    if (true) {
      System.out.println("after inner");
    }
  }

  private static class AnotherInner {
  }

  private static void afterAll() {
  }
}
