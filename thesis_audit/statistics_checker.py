"""Additional rule-based checks for statistical expression."""
from __future__ import annotations

from .models import NumberObservation, RiskFinding


def check_statistical_expressions(pdf_name: str, observations: list[NumberObservation]) -> list[RiskFinding]:
    """Detect non-standard or suspicious statistical expressions for MVP."""
    findings: list[RiskFinding] = []
    for obs in observations:
        if obs.type == "p_value" and obs.value == 0:
            findings.append(RiskFinding(pdf_name, obs.page_number, "nonstandard_p_zero", "low", "p should usually be reported as p < threshold instead of p = 0", f"发现不规范 p 值表达：{obs.raw}。", "建议复核统计软件输出，改用符合领域规范的 p 值表达。", context=obs.context))
        if obs.type == "mean_sd" and obs.secondary_value is not None and obs.value != 0 and abs(obs.secondary_value) > abs(obs.value) * 5:
            findings.append(RiskFinding(pdf_name, obs.page_number, "possible_high_variability", "low", "SD is more than five times the absolute mean", f"发现 SD 远大于均值：{obs.raw}。", "某些数据分布可能合理，但建议复核量纲、异常值和统计描述方式。", context=obs.context))
    return findings
