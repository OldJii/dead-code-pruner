class LambdaDispatchSample {
  fun setTransitionAt() {
    scheduleBeforeWork { println("prepare") }
  }

  fun release() {
    runOnWorker { println("release") }
  }

  fun draw() {
    withExecutionScope { println("draw") }
  }

  private fun withExecutionScope(draw: () -> Unit = {}) {
    println("bind")
    draw()
  }

  private inline fun scheduleBeforeWork(crossinline run: () -> Unit) {
    runCatching { run() }
  }

  private fun runOnWorker(runnable: () -> Unit) {
    runCatching(runnable)
  }
}
