"""Reproducible, manually labelled evaluation for the CampusFind matcher."""

import csv
import hashlib
import json
import os
import platform
import sys
from collections import defaultdict
from pathlib import Path

from ml.matcher import FEATURE_WEIGHTS, STOP_WORDS, rank_matches


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "ml" / "evaluation_dataset.csv"
RESULTS_JSON_PATH = ROOT / "ml" / "evaluation_results.json"
RESULTS_CSV_PATH = ROOT / "ml" / "evaluation_results.csv"
RETRIEVAL_K = (1, 3)

STRUCTURED_WEIGHTS = {
    "category_match": FEATURE_WEIGHTS["category_match"],
    "colour_similarity": FEATURE_WEIGHTS["colour_similarity"],
    "location_similarity": FEATURE_WEIGHTS["location_similarity"],
    "date_similarity": FEATURE_WEIGHTS["date_similarity"],
}


def effective_notification_threshold():
    backend_path = str(ROOT / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "campusfind.settings")
    from django.conf import settings

    return float(settings.NOTIFICATION_MATCH_MIN_SCORE)


def load_dataset():
    with DATASET_PATH.open(encoding="utf-8-sig", newline="") as dataset_file:
        rows = list(csv.DictReader(dataset_file))
    if not rows:
        raise ValueError("Evaluation dataset is empty.")

    pair_ids = set()
    groups = defaultdict(list)
    for row in rows:
        if row["pair_id"] in pair_ids:
            raise ValueError(f"Duplicate pair_id: {row['pair_id']}")
        pair_ids.add(row["pair_id"])
        if row["ground_truth"] not in {"0", "1"}:
            raise ValueError(f"Invalid ground truth for {row['pair_id']}")
        if row["source_type"] != "LOST" or row["candidate_type"] != "FOUND":
            raise ValueError(f"Unsupported report direction for {row['pair_id']}")
        if row["candidate_status"] != "OPEN":
            raise ValueError(f"Candidate must be OPEN for {row['pair_id']}")
        groups[row["query_id"]].append(row)

    for query_id, query_rows in groups.items():
        sources = {
            tuple(row[f"source_{field}"] for field in (
                "type", "title", "description", "category", "location", "date"
            ))
            for row in query_rows
        }
        if len(sources) != 1:
            raise ValueError(f"Source report differs within query {query_id}")
        if not any(row["ground_truth"] == "1" for row in query_rows):
            raise ValueError(f"Query {query_id} has no relevant candidate")
    return rows, groups


def item_from_row(row, prefix, report_id, status):
    return {
        "id": report_id,
        "type": row[f"{prefix}_type"],
        "status": status,
        "title": row[f"{prefix}_title"],
        "description": row[f"{prefix}_description"],
        "category": row[f"{prefix}_category"],
        "location": row[f"{prefix}_location"],
        "date": row[f"{prefix}_date"],
    }


def structured_score(details):
    available = [
        (weight, details[key])
        for key, weight in STRUCTURED_WEIGHTS.items()
        if details.get(key) is not None
    ]
    if not available:
        return 0.0
    weight_sum = sum(weight for weight, _ in available)
    return 100 * sum(weight * value for weight, value in available) / weight_sum


def confusion_metrics(y_true, y_pred):
    tp = sum(actual == 1 and predicted == 1 for actual, predicted in zip(y_true, y_pred))
    tn = sum(actual == 0 and predicted == 0 for actual, predicted in zip(y_true, y_pred))
    fp = sum(actual == 0 and predicted == 1 for actual, predicted in zip(y_true, y_pred))
    fn = sum(actual == 1 and predicted == 0 for actual, predicted in zip(y_true, y_pred))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "accuracy": (tp + tn) / len(y_true) if y_true else 0.0,
        "precision": precision,
        "recall": recall,
        "f1_score": 2 * precision * recall / (precision + recall)
        if precision + recall else 0.0,
    }


def retrieval_metrics(groups, scores_by_pair):
    results = {}
    for k in RETRIEVAL_K:
        precision_values = []
        recall_values = []
        for query_rows in groups.values():
            ranked = sorted(
                query_rows,
                key=lambda row: (-scores_by_pair[row["pair_id"]], row["pair_id"]),
            )
            top = ranked[:k]
            relevant_total = sum(row["ground_truth"] == "1" for row in query_rows)
            relevant_in_top = sum(row["ground_truth"] == "1" for row in top)
            precision_values.append(relevant_in_top / k)
            recall_values.append(relevant_in_top / relevant_total)
        results[f"precision_at_{k}"] = sum(precision_values) / len(precision_values)
        results[f"recall_at_{k}"] = sum(recall_values) / len(recall_values)
    return results


def configuration(threshold):
    return {
        "text": {
            "fields": ["title", "description"],
            "normalization": "Unicode casefold, then ASCII [a-z0-9]+ tokens",
            "stop_words": sorted(STOP_WORDS),
            "stemming_or_lemmatization": False,
            "terms": "Unigrams and adjacent bigrams after stop-word removal",
            "term_frequency": "Raw token/bigram counts",
            "inverse_document_frequency": "log((1 + document_count) / (1 + document_frequency)) + 1",
            "vector_normalization": "L2",
            "similarity": "Cosine dot product",
            "idf_scope": "Source report plus all eligible candidates for that query",
        },
        "feature_weights": dict(FEATURE_WEIGHTS),
        "colour_extraction": {
            "fields": ["title", "description"],
            "method": "Casefolded word-boundary tokens intersected with fixed vocabulary",
            "vocabulary": sorted({
                "black", "blue", "brown", "green", "grey", "gray", "orange",
                "pink", "purple", "red", "silver", "white", "yellow", "gold",
                "beige", "navy",
            }),
            "similarity": "Jaccard; feature omitted if either side has no detected colour",
        },
        "category": "Case-insensitive exact equality; omitted when either category is missing",
        "location": "Jaccard over casefolded [a-z0-9]+ token sets; omitted if either is missing",
        "date": "exp(-absolute_day_difference / 30); omitted if either date is missing or invalid",
        "missing_feature_handling": "Omit unavailable features and renormalize active weights",
        "score": "100 * weighted mean; rounded to two decimals by rank_matches",
        "notification_cutoff": {
            "value": threshold,
            "semantics": "Notifications are emitted at score >= this cutoff; API suggestions are not filtered by it",
        },
        "suggestion_limit": {
            "API_default": 10,
            "API_allowed_range": [1, 50],
            "UI_requested_limit": 10,
        },
    }


def run_evaluation():
    rows, groups = load_dataset()
    threshold = effective_notification_threshold()
    model_scores = {
        "hybrid": {},
        "text_only": {},
        "structured_only": {},
    }
    hybrid_ranks = {}

    for query_rows in groups.values():
        source = item_from_row(query_rows[0], "source", query_rows[0]["query_id"], "OPEN")
        candidates = [
            item_from_row(row, "candidate", row["pair_id"], row["candidate_status"])
            for row in query_rows
        ]
        ranked = rank_matches(source, candidates)
        matches = {result["candidate"]["id"]: result for result in ranked}
        hybrid_ranks.update({
            result["candidate"]["id"]: rank
            for rank, result in enumerate(ranked, start=1)
        })
        for row in query_rows:
            result = matches[row["pair_id"]]
            details = result["matching_details"]
            model_scores["hybrid"][row["pair_id"]] = result["similarity_score"]
            model_scores["text_only"][row["pair_id"]] = 100 * details["text_similarity"]
            model_scores["structured_only"][row["pair_id"]] = structured_score(details)

    y_true = [int(row["ground_truth"]) for row in rows]
    metrics_by_model = {}
    csv_rows = []
    for model_name, scores in model_scores.items():
        binary = confusion_metrics(
            y_true,
            [int(scores[row["pair_id"]] >= threshold) for row in rows],
        )
        ranking = retrieval_metrics(groups, scores)
        metrics = {**binary, **ranking}
        metrics_by_model[model_name] = metrics
        csv_rows.append({
            "model": model_name,
            "threshold": threshold,
            **metrics,
        })

    hybrid_cases = []
    robustness_by_scenario = defaultdict(list)
    for row in rows:
        pair_id = row["pair_id"]
        actual = int(row["ground_truth"])
        score = model_scores["hybrid"][pair_id]
        predicted = int(score >= threshold)
        case = {
            "pair_id": pair_id,
            "query_id": row["query_id"],
            "condition": row["scenario"],
            "ground_truth": actual,
            "manual_label_reason": row["manual_label_reason"],
            "hybrid_score": score,
            "hybrid_rank": hybrid_ranks[pair_id],
            "predicted_at_notification_cutoff": predicted,
            "status": "PASS" if predicted == actual else "FAIL",
        }
        hybrid_cases.append(case)
        robustness_by_scenario[row["scenario"]].append(case)

    positives = sum(y_true)
    output = {
        "dataset": {
            "file": "evaluation_dataset.csv",
            "sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
            "pairs": len(rows),
            "positive_pairs": positives,
            "negative_pairs": len(rows) - positives,
            "queries": len(groups),
            "construction": "Synthetic demo pairs manually annotated before scoring; no algorithm predictions used as labels",
            "limitations": [
                "Small, synthetic, manually authored dataset; it is not sampled from college-wide reports.",
                "Only LOST source to FOUND candidate direction is represented.",
                "Each query has four candidates and at least one manually labelled relevant candidate.",
                "Labels are scenario judgments; ambiguous or underspecified reports are labelled negative when identity cannot be established from the supplied evidence.",
                "Metrics describe this fixed demo set only and do not establish real-world performance.",
            ],
        },
        "evaluation": {
            "binary_decision": "score >= effective NOTIFICATION_MATCH_MIN_SCORE; this is the notification cutoff, not a match filter in the suggestions API",
            "threshold": threshold,
            "retrieval_metrics": "Macro-average over query groups; Precision@K divides relevant results in top K by K; Recall@K divides by relevant candidates in the query.",
            "retrieval_k": list(RETRIEVAL_K),
            "models": metrics_by_model,
        },
        "hybrid_pair_results": hybrid_cases,
        "robustness": [
            {
                "condition": condition,
                "pairs": len(cases),
                "passed": sum(case["status"] == "PASS" for case in cases),
                "failed": sum(case["status"] == "FAIL" for case in cases),
                "cases": cases,
            }
            for condition, cases in sorted(robustness_by_scenario.items())
        ],
        "configuration": configuration(threshold),
        "environment": {
            "python": sys.version.split()[0],
            "django": __import__("django").get_version(),
            "os": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "ml_libraries": "CampusFind matcher uses Python standard library only",
        },
    }

    RESULTS_JSON_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fieldnames = [
        "model", "threshold", "TP", "TN", "FP", "FN", "accuracy",
        "precision", "recall", "f1_score",
        "precision_at_1", "recall_at_1", "precision_at_3", "recall_at_3",
    ]
    with RESULTS_CSV_PATH.open("w", encoding="utf-8", newline="") as results_file:
        writer = csv.DictWriter(results_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow({key: row[key] for key in fieldnames})

    print(f"Dataset: {len(rows)} pairs, {positives} positive, {len(rows) - positives} negative")
    print(f"Effective notification cutoff: {threshold:g}")
    print("Model metrics (binary cutoff applies to notification eligibility only):")
    for name, metrics in metrics_by_model.items():
        print(
            f"{name}: TP={metrics['TP']} TN={metrics['TN']} "
            f"FP={metrics['FP']} FN={metrics['FN']} "
            f"accuracy={metrics['accuracy']:.4f} precision={metrics['precision']:.4f} "
            f"recall={metrics['recall']:.4f} F1={metrics['f1_score']:.4f} "
            f"P@1={metrics['precision_at_1']:.4f} R@1={metrics['recall_at_1']:.4f} "
            f"P@3={metrics['precision_at_3']:.4f} R@3={metrics['recall_at_3']:.4f}"
        )
    print(f"Wrote {RESULTS_JSON_PATH.relative_to(ROOT)} and {RESULTS_CSV_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    run_evaluation()
