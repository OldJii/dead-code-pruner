public enum EnumWithOverride {
  TYPE_A {
    @Override
    public boolean isSpecial() {
      return false;
    }
  },
  TYPE_B {
    @Override
    public boolean isSpecial() {
      return true;
    }
  },
  TYPE_C;

  // 这是基础方法，被 TYPE_A/TYPE_B override，不应被删除
  public boolean isSpecial() {
    return true;
  }

  // 这个方法没人 override，也不应被删除（因为是 enum）
  public boolean isEnabled() {
    return false;
  }

  public void doNothing() {
  }
}
