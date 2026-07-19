package demo
class Impl : ICallback {
  override fun onReady() {}
  override fun isEnabled(): Boolean = false

  companion object {
  }

  fun live() { println("live") }
}
