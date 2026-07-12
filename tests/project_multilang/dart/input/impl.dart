class Impl implements ICallback {
  @override
  void onReady() {}

  @override
  bool isEnabled() => false;

  static const String deadKey = "unused_ab_key";
  static bool _deadHelper() => deadKey == "x";

  void live() { print("live"); }
}
