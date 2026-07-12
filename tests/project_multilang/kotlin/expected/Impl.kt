package demo
class Impl : ICallback {
  override fun onReady() {}
  override fun isEnabled(): Boolean = false

  companion object {
    private const val DEAD_KEY = "unused_ab_key"
    private fun deadHelper(): Boolean = DEAD_KEY == "x"
  }

  fun live() { println("live") }
}
