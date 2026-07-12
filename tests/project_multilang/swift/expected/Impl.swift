class Impl: ICallback {
  func onReady() {}
  func isEnabled() -> Bool { return false }

  private static let deadKey = "unused_ab_key"

  func live() { print("live") }
}
