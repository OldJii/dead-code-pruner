package com.example;

class FeatureLauncher {
  boolean launch(Object container) {
    // A commented receiver call must not keep commentedOnly alive:
    // ServiceLocator.getInstance().getActionService().commentedOnly(container);
    return ServiceLocator.getInstance()
        .getActionService()
        .executeAction(container, "hot", "active", new Object());
  }
}
