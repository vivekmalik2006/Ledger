from core.boundary import check_permission_boundary, adjust_trust, TRUST_INCREMENT_THRESHOLD, TRUST_INCREMENT_PAISE


def test_within_limit_is_allowed(db_session, sample_user, sample_permission):
    result = check_permission_boundary(db_session, sample_user.id, sample_permission, "SIP", 5_000_00)
    assert result.allowed is True


def test_exceeding_limit_is_blocked(db_session, sample_user, sample_permission):
    result = check_permission_boundary(db_session, sample_user.id, sample_permission, "SIP", 15_000_00)
    assert result.allowed is False
    assert result.limit_paise == 10_000_00


def test_disallowed_product_is_blocked(db_session, sample_user, sample_permission):
    result = check_permission_boundary(db_session, sample_user.id, sample_permission, "EQUITY_SIP", 1_000_00)
    assert result.allowed is False


def test_adjust_trust_does_nothing_before_threshold(db_session, sample_permission):
    for _ in range(TRUST_INCREMENT_THRESHOLD - 1):
        result = adjust_trust(db_session, sample_permission)
        assert result is None


def test_adjust_trust_raises_limit_at_threshold(db_session, sample_permission):
    original_limit = sample_permission.max_auto_amount_paise
    for _ in range(TRUST_INCREMENT_THRESHOLD - 1):
        adjust_trust(db_session, sample_permission)
    result = adjust_trust(db_session, sample_permission)

    assert result["event"] == "LIMIT_ADJUSTED"
    assert sample_permission.max_auto_amount_paise == original_limit + TRUST_INCREMENT_PAISE


def test_adjust_trust_never_exceeds_absolute_ceiling(db_session, sample_permission):
    # Push the limit right up to just under the ceiling, then confirm one
    # more adjustment cycle triggers REAUTH_REQUIRED instead of overshooting.
    sample_permission.max_auto_amount_paise = sample_permission.absolute_ceiling_paise - 50_000  # 500 rupees under

    for _ in range(TRUST_INCREMENT_THRESHOLD - 1):
        adjust_trust(db_session, sample_permission)
    result = adjust_trust(db_session, sample_permission)

    assert result["event"] == "REAUTH_REQUIRED"
    # Critically: the limit must NOT have been pushed past the ceiling.
    assert sample_permission.max_auto_amount_paise <= sample_permission.absolute_ceiling_paise
