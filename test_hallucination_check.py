from backend.llm.hallucination_check import check_summary_grounding

SOURCE = (
    "Section 12A. Mandatory AI Automated Decision Audit Logs. Audit logs "
    "generated in connection with any automated decision-making system "
    "that processes personal data must be retained for a period of seven "
    "(7) years from the date of creation. Where an automated "
    "decision-making system is involved in a critical safety breach, the "
    "organisation must notify affected data subjects within twenty-four "
    "(24) hours of discovering the breach."
)


def test_accurate_summary_is_grounded():
    summary = (
        "Audit logs for automated decision-making systems must be kept for "
        "7 years, and affected individuals must be notified within 24 "
        "hours of a critical safety breach."
    )

    result = check_summary_grounding(SOURCE, summary)

    assert result.is_grounded
    assert result.unsupported_numbers == []


def test_fabricated_number_is_flagged():
    summary = (
        "Audit logs for automated decision-making systems must be kept for "
        "3 years, and affected individuals must be notified within 24 "
        "hours of a critical safety breach."
    )

    result = check_summary_grounding(SOURCE, summary)

    assert not result.is_grounded
    assert "3" in result.unsupported_numbers
    assert "24" not in result.unsupported_numbers


def test_off_topic_summary_has_low_overlap():
    summary = (
        "The quarterly earnings call covered marketing spend, hiring plans, "
        "and a new office lease signed last month."
    )

    result = check_summary_grounding(SOURCE, summary)

    assert not result.is_grounded
    assert result.word_overlap_ratio < 0.3


def test_empty_summary_is_trivially_grounded():
    result = check_summary_grounding(SOURCE, "")

    assert result.is_grounded
    assert result.word_overlap_ratio == 1.0


def test_notes_mentions_unsupported_numbers():
    summary = "Retention is now 3 years."

    result = check_summary_grounding(SOURCE, summary)

    assert "3" in result.notes
