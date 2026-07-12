package demo;
public class Impl implements ICallback {
  // contract — must keep even if empty / constant
  public void onReady() {}
  public boolean isEnabled() { return false; }

  private static final String DEAD_KEY = "unused_ab_key";
  private static boolean deadHelper() {
    return "x".equals(DEAD_KEY);
  }

  public void live() {
    System.out.println("live");
  }
}
