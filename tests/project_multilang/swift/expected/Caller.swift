func run(_ c: Any) {
  (c as! ICallback).onReady()
  if (c as! ICallback).isEnabled() {
    print("on")
  }
}

func multiline(flag: Bool) {
  use(false)
}

func use(_ b: Bool) { print(b) }
