"""Conservative callable-value reference forms shared by non-JVM adapters."""

import re


CALLABLE_VALUE_PATTERNS = (
    # Assignment, initializer, or named argument: ``callback = helper`` /
    # ``handler: helper``.  Calls are excluded because the normal call index
    # already handles them.
    re.compile(
        r'(?m)(?:=|:\s*)\s*'
        r'(?:(?:self|this)\s*\.\s*)?'
        r'([A-Za-z_]\w*)\b(?!\s*\()'),
    # Bare function passed as an argument: ``register(helper)``.
    re.compile(
        r'(?m)(?:\(|,)\s*'
        r'(?:(?:self|this)\s*\.\s*)?'
        r'([A-Za-z_]\w*)\s*(?=[,)])'),
)


__all__ = ['CALLABLE_VALUE_PATTERNS']
