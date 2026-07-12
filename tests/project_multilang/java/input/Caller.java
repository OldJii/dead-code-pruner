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
        !BuildConfig.IS_PRODUCTION
            && flag
            && other();
    use(isOneWay);
  }

  boolean other() { return true; }
  void use(boolean b) { System.out.println(b); }
}
