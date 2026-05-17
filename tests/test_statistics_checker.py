from thesis_audit.data_consistency_checker import extract_numbers_from_text
from thesis_audit.statistics_checker import check_statistical_expressions


def test_statistical_expression_warnings():
    nums = extract_numbers_from_text("p = 0\n12.0 ± 100.0", 1)
    findings = check_statistical_expressions("demo.pdf", nums)
    issue_types = {f.issue_type for f in findings}
    assert "nonstandard_p_zero" in issue_types
    assert "possible_high_variability" in issue_types
