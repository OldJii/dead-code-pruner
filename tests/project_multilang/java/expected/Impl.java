package demo;
public class Impl implements ICallback {
  // contract — must keep even if empty / constant
  public void onReady() {}
  public boolean isEnabled() { return false; }

  public void live() {
    System.out.println("live");
  }
}
