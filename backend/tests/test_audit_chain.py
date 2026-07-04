from core.audit_chain import append_audit_log, verify_chain


def test_fresh_chain_is_intact(db_session, sample_user):
    append_audit_log(
        db_session, user_id=sample_user.id, action="CREATE_SIP",
        reason="test", rule_checked="TEST", status="ACTED", amount_paise=5_000_00,
    )
    result = verify_chain(db_session, sample_user.id)
    assert result["intact"] is True


def test_chain_survives_multiple_appends(db_session, sample_user):
    for i in range(5):
        append_audit_log(
            db_session, user_id=sample_user.id, action="CREATE_SIP",
            reason=f"entry {i}", rule_checked="TEST", status="ACTED", amount_paise=1_000_00,
        )
    result = verify_chain(db_session, sample_user.id)
    assert result["intact"] is True


def test_tampering_with_a_row_breaks_the_chain(db_session, sample_user):
    """
    This is the test that actually proves the 'immutable audit trail'
    claim rather than just asserting it. We append three rows, then
    directly mutate the middle row's content (bypassing append_audit_log,
    simulating an attempted tamper) and confirm verify_chain() detects it.
    """
    append_audit_log(db_session, user_id=sample_user.id, action="A", reason="first", rule_checked="T", status="ACTED", amount_paise=1_000_00)
    middle = append_audit_log(db_session, user_id=sample_user.id, action="B", reason="second", rule_checked="T", status="ACTED", amount_paise=2_000_00)
    append_audit_log(db_session, user_id=sample_user.id, action="C", reason="third", rule_checked="T", status="ACTED", amount_paise=3_000_00)

    # Simulate tampering: directly rewrite a past row's reason without
    # going through append_audit_log (which is the only path that computes
    # a correct hash).
    middle.reason = "tampered reason — this should be detected"
    db_session.commit()

    result = verify_chain(db_session, sample_user.id)
    assert result["intact"] is False
    assert result["broken_at_id"] == middle.id


def test_chains_are_independent_per_user(db_session, sample_user):
    other_user_id = sample_user.id + 999  # doesn't need to exist for this check
    append_audit_log(db_session, user_id=sample_user.id, action="A", reason="x", rule_checked="T", status="ACTED", amount_paise=1_000_00)
    append_audit_log(db_session, user_id=other_user_id, action="A", reason="y", rule_checked="T", status="ACTED", amount_paise=1_000_00)

    assert verify_chain(db_session, sample_user.id)["intact"] is True
    assert verify_chain(db_session, other_user_id)["intact"] is True
