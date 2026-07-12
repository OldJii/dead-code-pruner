package regression;

class ImageNetSpeedListener {
  static void bs() {}
}

class CropIwaLog {
  static void d(String format, Object... args) {}

  static void e(String message, Throwable error) {}

  static void unusedLongName(int value) {
    System.out.println(value);
  }
}

class XmlCallbacks {
  public void onTap() {}
}

class FieldConstantsA {
  public static final String LIVE = "live"; // trailing comment must not bind forward
  public static final String DEAD = "dead"; // genuinely unused
  public static final String SHARED = "a";

  boolean isLive(String value) {
    return LIVE.equals(value);
  }
}

class FieldConstantsB {
  public static final String SHARED = "b";
  public static final String MULTI_LIVE = "live", MULTI_UNUSED = "unused";
}

@interface FrameworkEntry {}
@interface GeneratedField {}

class AnnotatedApi {
  public static final String ALIGN = "align"; // trailing comment belongs to the field

  @FrameworkEntry
  public static void register(String value) {
    System.out.println(value);
  }

  @GeneratedField
  public static final String GENERATED_OBSERVER = "generatedObserver";
}

class StaticApiBase {
  public static String inheritedApi(String value) {
    return value.trim();
  }

  public static String importedApi(String value) {
    return value.trim();
  }
}

class StaticApiMiddle extends StaticApiBase {}
