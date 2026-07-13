package demo
fun run(c: Any) {
  (c as ICallback).onReady()
  if ((c as ICallback).isEnabled()) {
    println("on")
  }
}

fun multiline(flag: Boolean) {
  val isOneWay =
      !FEATURE_FLAG
          && flag
          && other()
  use(isOneWay)
}

fun other(): Boolean = true
fun use(b: Boolean) { println(b) }
