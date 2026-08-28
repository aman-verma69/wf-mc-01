def requires_explicit_confirmation(intent: str) -> bool:
    return intent == "CONFIRM_PURCHASE"
