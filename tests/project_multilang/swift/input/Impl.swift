class Impl: ICallback {
  func onReady() {}
  func isEnabled() -> Bool { return false }

  private static let deadKey = "unused_ab_key"
  private static func deadHelper() -> Bool { return deadKey == "x" }

  func live() { print("live") }
}
