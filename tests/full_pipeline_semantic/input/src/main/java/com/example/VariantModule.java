package com.example;

class VariantModule {
  void init() {
    if (BuildConfig.DEBUG_BUILD) {
      VariantHook.hook();
    }
  }
}
