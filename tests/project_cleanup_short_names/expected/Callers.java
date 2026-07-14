package regression;

class Callers {
  void fetch() {
  }

  void load(String uri, Throwable error) {
    SampleLog.d("load {%s}", uri);
    SampleLog.e(error.getMessage(), error);
  }

  String shared() {
    return FieldConstantsA.SHARED + FieldConstantsB.SHARED + FieldConstantsB.MULTI_LIVE
        + AnnotatedApi.ALIGN;
  }
}
