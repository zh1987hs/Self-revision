from thesis_audit.data_consistency_checker import extract_numbers_from_text, check_invalid_ranges, check_sum_lines


def test_extract_numbers():
    text = "提高了 35.2 %\np < 0.05\nR²=0.98\nPearson r = 0.85\n结果为 12.3 ± 1.5\n浓度 1.2 × 10^-3"
    nums = extract_numbers_from_text(text, 2)
    types = {n.type for n in nums}
    assert "percentage" in types
    assert "p_value" in types
    assert "r2" in types
    assert "correlation" in types
    assert "mean_sd" in types
    assert any(abs(n.value - 0.0012) < 1e-12 for n in nums)


def test_invalid_ranges():
    text = "p = 1.2\nR2 = 1.5\nr = 1.4\nmean 12.3 ± -1.5"
    nums = extract_numbers_from_text(text, 1)
    findings = check_invalid_ranges("demo.pdf", nums)
    issue_types = {f.issue_type for f in findings}
    assert "invalid_p_value_range" in issue_types
    assert "invalid_r2_range" in issue_types
    assert "invalid_correlation_range" in issue_types
    assert "negative_standard_deviation" in issue_types


def test_sum_check():
    findings = check_sum_lines("demo.pdf", "A B C 合计 10 20 40", 1)
    assert findings
    assert findings[0].issue_type == "sum_total_mismatch"
