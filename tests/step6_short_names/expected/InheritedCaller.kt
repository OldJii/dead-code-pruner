package regression

class InheritedCaller : StaticApiMiddle() {
  fun call(value: String): String = inheritedApi(value)
}
