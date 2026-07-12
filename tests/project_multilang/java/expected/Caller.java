package demo;
public class Caller {
  void run(Object c) {
    ((ICallback) c).onReady();
    if (((ICallback) c).isEnabled()) {
      System.out.println("on");
    }
  }

  void multiline(boolean flag) {
    boolean isOneWay =
        false;
    use(isOneWay);
  }

  void use(boolean b) { System.out.println(b); }
}
