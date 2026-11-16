"""Explainable TF-IDF matching for CampusFind lost and found reports."""

from datetime import date, datetime
from collections import Counter
import math
import re
from typing import Any, Mapping, Sequence

VALID_TYPES = {"LOST", "FOUND"}
FEATURE_WEIGHTS = {
    "text_similarity": 0.55,
    "category_match": 0.15,
    "colour_similarity": 0.10,
    "location_similarity": 0.12,
    "date_similarity": 0.08,
}
COLOURS = {
    "black", "blue", "brown", "green", "grey", "gray", "orange", "pink",
    "purple", "red", "silver", "white", "yellow", "gold", "beige", "navy",
}
STOP_WORDS = {
    "a", "an", "and", "at", "by", "for", "from", "in", "is", "it", "of",
    "on", "or", "the", "to", "was", "with",
}


def _text(item: Mapping[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "").strip()
        for field in ("title", "description")
        if str(item.get(field) or "").strip()
    )


def _colours(item: Mapping[str, Any]) -> set[str]:
    return set(re.findall(r"\b[\w-]+\b", _text(item).casefold())) & COLOURS


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
    return None


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _cosine_similarity(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return sum(weight * right.get(term, 0.0) for term, weight in left.items())


def _location_tokens(item: Mapping[str, Any]) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(item.get("location") or "").casefold()))


def _category_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool | None:
    left_category = str(left.get("category") or "").strip().casefold()
    right_category = str(right.get("category") or "").strip().casefold()
    if not left_category or not right_category:
        return None
    return left_category == right_category


def _text_similarities(source: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> list[float]:
    documents = [_text(source), *(_text(candidate) for candidate in candidates)]
    term_counts = []
    for document in documents:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", document.casefold())
            if token not in STOP_WORDS
        ]
        terms = tokens + [f"{left} {right}" for left, right in zip(tokens, tokens[1:])]
        term_counts.append(Counter(terms))

    document_frequency = Counter(
        term for counts in term_counts for term in counts
    )
    document_count = len(term_counts)
    inverse_document_frequency = {
        term: math.log((1 + document_count) / (1 + frequency)) + 1
        for term, frequency in document_frequency.items()
    }
    tfidf_vectors = []
    for counts in term_counts:
        vector = {
            term: count * inverse_document_frequency[term]
            for term, count in counts.items()
        }
        magnitude = math.sqrt(sum(weight * weight for weight in vector.values()))
        if magnitude:
            vector = {term: weight / magnitude for term, weight in vector.items()}
        tfidf_vectors.append(vector)

    source_vector = tfidf_vectors[0]
    return [
        _cosine_similarity(source_vector, tfidf_vectors[index])
        for index in range(1, len(tfidf_vectors))
    ]


def rank_matches(
    source: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Rank open reports of the opposite type and explain each score.

    Scores are weighted similarities on a 0-100 scale, not prediction accuracy.
    Missing structured features are omitted and the remaining weights are
    normalized so incomplete reports can still be compared safely.
    """
    source_type = str(source.get("type") or "").upper()
    if source_type not in VALID_TYPES:
        raise ValueError("Report type must be LOST or FOUND.")
    if source.get("status") and str(source["status"]).upper() != "OPEN":
        raise ValueError("Only OPEN reports can be matched.")

    opposite_type = "FOUND" if source_type == "LOST" else "LOST"
    eligible = []
    for candidate in candidates:
        candidate_type = str(candidate.get("type") or "").upper()
        if candidate_type not in VALID_TYPES:
            raise ValueError("Candidate report type must be LOST or FOUND.")
        if candidate_type != opposite_type:
            continue
        if candidate.get("status") and str(candidate["status"]).upper() != "OPEN":
            continue
        source_id = source.get("id")
        if source_id is not None and candidate.get("id") == source_id:
            continue
        eligible.append(candidate)

    text_scores = _text_similarities(source, eligible)
    results = []
    for candidate, text_score in zip(eligible, text_scores):
        details: dict[str, Any] = {"text_similarity": round(float(text_score), 4)}
        weighted_values = [(FEATURE_WEIGHTS["text_similarity"], float(text_score))]

        category_match = _category_match(source, candidate)
        details["category_match"] = category_match
        if category_match is not None:
            weighted_values.append((FEATURE_WEIGHTS["category_match"], float(category_match)))

        source_colours = _colours(source)
        candidate_colours = _colours(candidate)
        colour_matches = sorted(source_colours & candidate_colours)
        details["source_colours"] = sorted(source_colours)
        details["candidate_colours"] = sorted(candidate_colours)
        details["colour_matches"] = colour_matches
        if source_colours and candidate_colours:
            colour_score = _jaccard(source_colours, candidate_colours)
            details["colour_similarity"] = round(colour_score, 4)
            weighted_values.append((FEATURE_WEIGHTS["colour_similarity"], colour_score))
        else:
            details["colour_similarity"] = None

        source_location = _location_tokens(source)
        candidate_location = _location_tokens(candidate)
        if source_location and candidate_location:
            location_score = _jaccard(source_location, candidate_location)
            details["location_similarity"] = round(location_score, 4)
            weighted_values.append((FEATURE_WEIGHTS["location_similarity"], location_score))
        else:
            details["location_similarity"] = None

        source_date = _as_date(source.get("date"))
        candidate_date = _as_date(candidate.get("date"))
        if source_date and candidate_date:
            difference = abs((source_date - candidate_date).days)
            date_score = math.exp(-difference / 30)
            details["date_difference_days"] = difference
            details["date_similarity"] = round(date_score, 4)
            weighted_values.append((FEATURE_WEIGHTS["date_similarity"], date_score))
        else:
            details["date_difference_days"] = None
            details["date_similarity"] = None

        total_weight = sum(weight for weight, _ in weighted_values)
        score = 100 * sum(weight * value for weight, value in weighted_values) / total_weight
        results.append({
            "candidate": candidate,
            "similarity_score": round(score, 2),
            "matching_details": details,
        })

    results.sort(
        key=lambda result: (
            -result["similarity_score"],
            str(result["candidate"].get("id", "")),
        )
    )
    return results[:limit] if limit is not None else results