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
    System.out.println("after inner");
  }

  private static class AnotherInner {
  }

}
