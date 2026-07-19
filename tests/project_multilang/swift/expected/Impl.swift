class Impl: ICallback {
  func onReady() {}
  func isEnabled() -> Bool { return false }

  func live() { print("live") }
}
