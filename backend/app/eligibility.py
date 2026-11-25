from typing import Optional
from pydantic import BaseModel


class StudentProfile(BaseModel):
    branch: str = "ALL"           # e.g., "CS", "IT", "AIML", "EXTC"
    year: str = "ALL"             # e.g., "FE", "SE", "TE", "BE"
    category: str = "OPEN"        # e.g., "OPEN", "OBC", "SC", "ST", "EBC"
    cgpa: Optional[float] = None
    family_income: Optional[int] = None
    active_backlogs: int = 0


def evaluate_eligibility(canonical: dict, profile: StudentProfile) -> dict:
    """
    100% Deterministic System Code (0 AI tokens).
    Compares StudentProfile against CanonicalNotice['hard_rules'] and flags edge_conditions.
    """
    rules = canonical.get("hard_rules", {})
    edge_conditions = canonical.get("edge_conditions", [])
    citation = rules.get("citation")

    failed_reasons = []
    passed_checks = []
    is_general = True

    # 1. Branch check
    allowed_branches = [b.strip().upper() for b in rules.get("target_branches", ["ALL"])]
    if "ALL" not in allowed_branches:
        is_general = False
        if profile.branch.strip().upper() not in allowed_branches:
            failed_reasons.append(
                f"Branch '{profile.branch}' not in allowed branches: {', '.join(allowed_branches)}"
            )
        else:
            passed_checks.append(f"Branch '{profile.branch}' matches")

    # 2. Year check
    allowed_years = [y.strip().upper() for y in rules.get("target_years", ["ALL"])]
    if "ALL" not in allowed_years:
        is_general = False
        if profile.year.strip().upper() not in allowed_years:
            failed_reasons.append(
                f"Year '{profile.year}' not in allowed years: {', '.join(allowed_years)}"
            )
        else:
            passed_checks.append(f"Year '{profile.year}' matches")

    # 3. Category check
    allowed_cats = [c.strip().upper() for c in rules.get("target_categories", ["ALL"])]
    if "ALL" not in allowed_cats:
        is_general = False
        if profile.category.strip().upper() not in allowed_cats:
            failed_reasons.append(
                f"Category '{profile.category}' not in allowed categories: {', '.join(allowed_cats)}"
            )
        else:
            passed_checks.append(f"Category '{profile.category}' matches")

    # 4. Minimum CGPA check
    min_cgpa = rules.get("min_cgpa")
    if min_cgpa is not None:
        is_general = False
        if profile.cgpa is None:
            failed_reasons.append(f"Requires minimum CGPA {min_cgpa} (your CGPA is not set)")
        elif profile.cgpa < min_cgpa:
            failed_reasons.append(f"CGPA {profile.cgpa} is below required minimum {min_cgpa}")
        else:
            passed_checks.append(f"CGPA {profile.cgpa} >= {min_cgpa}")

    # 5. Maximum Family Income check
    max_income = rules.get("max_income")
    if max_income is not None:
        is_general = False
        if profile.family_income is None:
            failed_reasons.append(f"Requires annual income <= ₹{max_income:,} (your income is not set)")
        elif profile.family_income > max_income:
            failed_reasons.append(f"Family income ₹{profile.family_income:,} exceeds limit ₹{max_income:,}")
        else:
            passed_checks.append(f"Family income ₹{profile.family_income:,} <= ₹{max_income:,}")

    # 6. Maximum Backlogs check
    max_backlogs = rules.get("max_backlogs")
    if max_backlogs is not None:
        is_general = False
        if profile.active_backlogs > max_backlogs:
            failed_reasons.append(
                f"Active backlogs ({profile.active_backlogs}) exceed allowed limit ({max_backlogs})"
            )
        else:
            passed_checks.append(f"Active backlogs ({profile.active_backlogs}) <= {max_backlogs}")

    # Determine final verdict
    if failed_reasons:
        status = "Not Eligible"
    elif is_general:
        status = "General Notice"
    else:
        status = "Eligible"

    return {
        "status": status,
        "citation": citation,
        "passed_checks": passed_checks,
        "failed_reasons": failed_reasons,
        "edge_warnings": edge_conditions,  # Surface nuanced conditions with their C# tags
    }