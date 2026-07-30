import re
from typing import Any, Iterable, Optional


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    text = str(value).strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _tokens(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    tokens: set[str] = set()
    for item in values:
        if isinstance(item, str):
            cleaned = _normalize(item)
            if cleaned:
                tokens.update({part for part in cleaned.split() if len(part) > 1})
        elif item is not None:
            cleaned = _normalize(item)
            if cleaned:
                tokens.update({part for part in cleaned.split() if len(part) > 1})
    return tokens


def profile_terms(user: Any) -> set[str]:
    terms: set[str] = set()
    if not user:
        return terms

    for field in [
        getattr(user, "studyDomain", None),
        getattr(user, "workDomain", None),
        getattr(user, "jobTitle", None),
        getattr(user, "institutionType", None),
        getattr(user, "roleType", None),
        getattr(user, "location", None),
    ]:
        terms.update(_tokens(field))

    for skill in getattr(user, "skills", []) or []:
        terms.update(_tokens(skill))
    return terms


def score_profile_match(current_user: Any, candidate: Any) -> int:
    if not current_user:
        return 0

    current_terms = profile_terms(current_user)
    candidate_terms = profile_terms(candidate)
    overlap = current_terms & candidate_terms
    score = len(overlap) * 3

    current_role = getattr(current_user, "roleType", None)
    candidate_role = getattr(candidate, "roleType", None)
    if current_role and candidate_role and current_role == candidate_role:
        score += 2

    current_location = getattr(current_user, "location", None)
    candidate_location = getattr(candidate, "location", None)
    if current_location and candidate_location and _normalize(current_location) == _normalize(candidate_location):
        score += 2

    current_study = getattr(current_user, "studyDomain", None)
    candidate_study = getattr(candidate, "studyDomain", None)
    if current_study and candidate_study and _normalize(current_study) == _normalize(candidate_study):
        score += 4

    current_work = getattr(current_user, "workDomain", None)
    candidate_work = getattr(candidate, "workDomain", None)
    if current_work and candidate_work and _normalize(current_work) == _normalize(candidate_work):
        score += 4

    current_skills = set(_tokens(getattr(current_user, "skills", []) or []))
    candidate_skills = set(_tokens(getattr(candidate, "skills", []) or []))
    score += len(current_skills & candidate_skills) * 2

    return score


def score_document_match(current_user: Any, document: Any) -> int:
    if not current_user:
        return 0

    current_terms = profile_terms(current_user)
    text_fields = [
        getattr(document, "title", None),
        getattr(document, "category", None),
        getattr(document, "description", None),
        getattr(document, "associatedCourse", None),
        getattr(document, "publisher", None),
    ]
    document_terms = set()
    for field in text_fields:
        document_terms.update(_tokens(field))
    for tag in getattr(document, "tags", []) or []:
        document_terms.update(_tokens(tag))

    score = len(current_terms & document_terms) * 3

    current_study = getattr(current_user, "studyDomain", None)
    document_category = getattr(document, "category", None)
    if current_study and document_category and _normalize(current_study) in _normalize(document_category):
        score += 4

    if getattr(document, "isPremium", False) and getattr(current_user, "isPremium", False):
        score += 1

    return score


def score_opportunity_match(current_user: Any, opportunity: Any) -> int:
    if not current_user:
        return 0

    current_terms = profile_terms(current_user)
    opportunity_terms = set()
    for field in [
        getattr(opportunity, "title", None),
        getattr(opportunity, "description", None),
        getattr(opportunity, "organization", None),
        getattr(opportunity, "domain", None),
        getattr(opportunity, "targetAudience", None),
    ]:
        opportunity_terms.update(_tokens(field))
    for tag in getattr(opportunity, "tags", []) or []:
        opportunity_terms.update(_tokens(tag))

    score = len(current_terms & opportunity_terms) * 3

    current_study = getattr(current_user, "studyDomain", None)
    opportunity_domain = getattr(opportunity, "domain", None)
    if current_study and opportunity_domain and _normalize(current_study) in _normalize(opportunity_domain):
        score += 4

    if getattr(current_user, "roleType", None) and getattr(opportunity, "targetAudience", None):
        if _normalize(current_user.roleType) in _normalize(opportunity.targetAudience):
            score += 2

    return score


def score_feed_post_match(current_user: Any, post: Any) -> int:
    if not current_user:
        return 0

    current_terms = profile_terms(current_user)
    author = getattr(post, "author", None)
    author_terms = profile_terms(author)
    post_terms = set()
    for field in [getattr(post, "title", None), getattr(post, "content", None)]:
        post_terms.update(_tokens(field))

    score = len((current_terms | author_terms) & post_terms) * 2

    current_study = getattr(current_user, "studyDomain", None)
    author_study = getattr(author, "studyDomain", None)
    if current_study and author_study and _normalize(current_study) == _normalize(author_study):
        score += 4

    current_work = getattr(current_user, "workDomain", None)
    author_work = getattr(author, "workDomain", None)
    if current_work and author_work and _normalize(current_work) == _normalize(author_work):
        score += 4

    return score
