package io.github.oldjii;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

public final class RegressionCases {
    @Getter
    @AllArgsConstructor
    public enum ServerStatus {
        READY("ready", "[R] "),
        DONE("done", "[D] ");

        private final String code;
        private final String titlePrefix;

        public boolean isTerminal() {
            return this == DONE;
        }
    }

    @RequiredArgsConstructor
    public static final class RequiredConfig {
        private final String required;
        private final String initialized = "default";

        public String describe() {
            return required + initialized;
        }
    }

    @Data
    public static final class RuntimeConfig {
        private boolean enable = false;
        private String externalValue;

        public boolean needPreload(boolean whitelistHit) {
            return enable || whitelistHit;
        }
    }

    public static String exercise() {
        RuntimeConfig config = new RuntimeConfig();
        config.setExternalValue("external");
        RequiredConfig required = new RequiredConfig("required");
        return ServerStatus.READY.getTitlePrefix()
                + required.describe()
                + config.getExternalValue()
                + config.needPreload(true);
    }
}
