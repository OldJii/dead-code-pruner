void run(Object c) {
  (c as ICallback).onReady();
  if ((c as ICallback).isEnabled()) {
    print("on");
  }
}

void multiline(bool flag) {
  bool isOneWay =
      false;
  use(isOneWay);
}

void use(bool b) { print(b); }
