func run(_ c: Any) {
  (c as! ICallback).onReady()
  if (c as! ICallback).isEnabled() {
    print("on")
  }
}

func multiline(flag: Bool) {
  let isOneWay =
      !INTL_FLAG
          && flag
          && other()
  use(isOneWay)
}

func other() -> Bool { return true }
func use(_ b: Bool) { print(b) }
