package demo
fun run(c: Any) {
  (c as ICallback).onReady()
  if ((c as ICallback).isEnabled()) {
    println("on")
  }
}

fun multiline(flag: Boolean) {
  use(false)
}

fun use(b: Boolean) { println(b) }
