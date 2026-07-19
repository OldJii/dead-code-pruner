class Impl implements ICallback {
  @override
  void onReady() {}

  @override
  bool isEnabled() => false;

  void live() { print("live"); }
}
