# CampusFind Matching Evaluation

## Summary

The existing `ml.matcher.rank_matches` implementation was evaluated without
changing production matching logic. This is a fixed, synthetic demonstration
benchmark, not a sample of real campus reports and not evidence of
college-wide performance.

| Dataset property | Value |
| --- | ---: |
| Manually labelled LOST-to-FOUND pairs | 32 |
| Positive pairs | 8 |
| Negative pairs | 24 |
| Query reports | 8 |
| Candidate reports per query | 4 |
| Effective notification cutoff | 35.0 |
| Positive-label source | Manual scenario reasoning, recorded per row |

The CSV has `manual_label_reason` for every independently assigned label.
Labels were written as scenario judgments, not generated from matcher
predictions. Ambiguous/generic pairs are negative when their supplied evidence
does not identify the same physical item. Descriptions and locations are
synthetic. The dataset includes missing descriptions, incomplete fields,
colour variations, spelling noise, alternative wording, long text, similar
but distinct objects, category differences, and date/location variation.

The fixed data is too small and deliberately constructed for a train/validation
/test split to be meaningful. The matcher does not train a persistent model:
it computes TF-IDF from each source report and its eligible candidate pool at
request time.

## Method

For each query, the evaluator calls the production `rank_matches` once with
all four candidates, preserving its candidate-pool IDF and ranking behavior.
Binary metrics use the effective `NOTIFICATION_MATCH_MIN_SCORE` from Django
settings. Its current effective value is **35.0**. At the cutoff, a candidate
is notification-eligible at score >= 35.

Important distinction: 35.0 is a **notification cutoff**, not a cutoff in the
matching suggestions API. The API returns ranked suggestions (default top 10,
allowed 1–50); the frontend requests 10. Similarity scores are not probabilities
or accuracy percentages.

Precision@K and Recall@K are macro-averaged over the eight LOST queries. Each
query has four candidates, so K=1 and K=3 are reported. Precision@K divides
relevant candidates in the top K by K; Recall@K divides by the number of
relevant candidates for that query.

Two comparison baselines were computed by the evaluation script on the same
examples:

* **Text-only:** the existing matcher’s TF-IDF/cosine component alone.
* **Structured-only:** category, colour, location, and date details from the
  existing matcher, weighted with the existing structured weights and
  renormalized over available features. No production code was changed.

The same threshold was used for all three binary comparisons. Retrieval metrics
use each approach's own scores and ranking. No unrelated algorithm was added.

## Table A — ML Evaluation Results

Results below refer to the **notification-cutoff binary decision** unless
marked as a retrieval metric.

| Metric | Hybrid value | Interpretation for LOST/FOUND matching |
| --- | ---: | --- |
| Accuracy | 0.5938 (59.38%) | Fraction of the 32 candidate pairs whose cutoff decision agreed with the manual label. |
| Precision | 0.3810 (38.10%) | Of pairs at/above the cutoff, fraction manually labelled as the same item. |
| Recall / sensitivity | 1.0000 (100%) | Fraction of the 8 manually relevant pairs at/above the cutoff. |
| F1-score | 0.5517 (55.17%) | Harmonic mean of precision and recall. |
| Precision@1 | 0.7500 (75.00%) | Mean fraction relevant in the single top-ranked suggestion per query. |
| Recall@1 | 0.7500 (75.00%) | Mean fraction of each query's relevant candidate(s) retrieved at rank 1. |
| Precision@3 | 0.3333 (33.33%) | Mean relevant fraction among the top 3 suggestions per query. |
| Recall@3 | 1.0000 (100%) | Mean fraction of relevant candidates retrieved within the top 3. |

The hybrid cutoff yields no false negatives on this small set but produces 13
false positives among 24 negative pairs. This is consistent with the high
observed recall and low precision at the current notification cutoff; it is not
a claim about real-world rates. Lowering a cutoff generally admits more
suggestions (potentially increasing recall and false positives); raising it
usually suppresses both. This evaluation did not tune or change the production
cutoff.

## Table B — Hybrid Confusion Matrix

| Actual \ Predicted | Positive (score >= 35) | Negative (score < 35) |
| --- | ---: | ---: |
| Positive (same item) | TP = 8 | FN = 0 |
| Negative (different / insufficient evidence) | FP = 13 | TN = 11 |

Definitions in this context: TP is a relevant LOST/FOUND pair admitted at the
notification cutoff; TN is an unrelated or insufficiently supported pair
below it; FP is an unrelated pair admitted; FN is a relevant pair below it.

## Table C — Model Comparison

| Approach | Accuracy | Precision | Recall | F1-score | Precision@1 | Recall@1 | Precision@3 | Recall@3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Text-only TF-IDF/cosine | 0.8438 | 1.0000 | 0.3750 | 0.5455 | 1.0000 | 1.0000 | 0.3333 | 1.0000 |
| Structured-feature-only | 0.3438 | 0.2759 | 1.0000 | 0.4324 | 0.1250 | 0.1250 | 0.2500 | 0.7500 |
| Existing hybrid | 0.5938 | 0.3810 | 1.0000 | 0.5517 | 0.7500 | 0.7500 | 0.3333 | 1.0000 |

At the same cutoff, text-only has the highest accuracy and precision but misses
5 of 8 positive pairs. Structured-only admits all positive pairs but also 21
negative pairs. Hybrid ranks 6 of 8 positives first and retrieves all 8 within
the top 3. These results are specific to this constructed dataset and cutoff;
they do not establish that one approach is generally superior.

## Table D — Robustness Evaluation

For this table, PASS means the hybrid cutoff decision agrees with the manually
assigned pair label. “Mixed” means the condition has both correct and incorrect
decisions. Detailed results for every pair, including score, rank, label,
decision, and status, are in `evaluation_results.json`.

| Test condition | Expected behavior | Observed behavior | Status |
| --- | --- | --- | --- |
| Missing descriptions | Use remaining title/structured evidence; generic reports should not be treated as certain matches. | Q2-C1 relevant sparse pair: 57.38, rank 1, PASS. Q2-C4 generic incomplete pair: 12.92, rank 4, PASS. A red bottle, Q2-C3, scores 43.80 and is a false positive. | Mixed |
| Short / partially informative text | Relevant reports should rank using available evidence, while generic or conflicting reports should remain distinguishable. | Q3-C1 alternative wording ranks 2nd at 45.79, PASS. Q3-C2 conflicting backpack ranks 1st at 50.72; Q3-C3 scores 41.82. Both are false positives. | Mixed |
| Spelling variation | Character-level correction is not present; overlap from other terms/features may still rank the pair. | Misspelled umbrella Q4-C1 scores 45.62, rank 1, PASS. A different black umbrella Q4-C3 scores 44.85, false positive. | Mixed |
| Missing colour | Do not require colour when not reported; omit unavailable colour similarity. | Relevant single earbud Q5-C1 has no reported colour and scores 47.64, PASS. Similar but different earbuds/case Q5-C2/C3 score 42.01/38.60, false positives. | Mixed |
| Different wording | Shared identifying marks should support semantically related descriptions, within the implementation's token-overlap limits. | Q8-C1 alternative sketchbook wording scores 47.00, rank 1, PASS. A blue notebook without the matching drawing Q8-C2 scores 44.88, false positive. | Mixed |
| Similar name, different physical item | Conflicting identifying details should prevent a confident match. | Wallet Q1-C2 scores 61.04 and wrong backpack Q3-C2 scores 50.72, both above cutoff despite conflicting details. | Fail for these cases |
| Different locations / dates | The date and location features should affect score but should not independently establish identity. | Ring Q6-C1 with a 3-day date difference and different location wording scores 50.38, rank 2, PASS. Unrelated pendant Q6-C3 scores 51.79, rank 1; bracelet Q6-C4 scores 41.05; both false positives. | Mixed |
| Long descriptions | Retain identifying detail without an unrelated model/name becoming a match. | Calculator Q7-C1 scores 69.89, rank 1, PASS. A different same-model calculator Q7-C2 scores 38.73 and is a false positive. | Mixed |
| Different category / unrelated item | Category mismatch and unrelated text should lower score. | Chemistry notebook Q7-C4 scores 25.92; star notebook Q3-C4 scores 31.03; both are below cutoff. | Pass for these cases |
| Incomplete fields plus distant date/location | Missing features should be omitted and remaining weights renormalized; sparse candidates should not gain a high score from absence alone. | Generic candidates Q4-C4 and Q8-C4 score 16.00 and 12.93, respectively; both are correctly below cutoff. | Pass for these cases |

Robustness is not uniformly successful. In particular, colour and exact
identifying conflicts do not always overcome shared text/category/location
signals. The matcher has no spelling-correction, entity-resolution, or
item-identity model.

## Table H — Actual ML Configuration

| Component | Actual implementation |
| --- | --- |
| ML dependencies | Python standard library only; no scikit-learn, NumPy, neural network, or persisted model. |
| Input text | `title` and `description`, joined with a space when non-empty. |
| Tokenization | `casefold()` followed by regex `[a-z0-9]+`; punctuation is discarded. |
| Stop words | Fixed set of 17 words, recorded in `evaluation_results.json`. |
| Stemming / lemmatization | None. |
| N-grams | Unigrams plus adjacent bigrams formed after stop-word removal. |
| Term frequency | Raw occurrence count. |
| IDF | `log((1 + N) / (1 + df)) + 1`; calculated over the source plus eligible candidates for that query. |
| Vector normalization / similarity | L2-normalized vectors; cosine similarity calculated as a dot product. |
| Hybrid feature weights | Text 0.55; category 0.15; colour 0.10; location 0.12; date 0.08. |
| Category | Case-insensitive exact equality; omitted if either value is missing. |
| Colour extraction | Word tokens in title/description intersected with fixed 16-colour vocabulary; Jaccard similarity; omitted if either report has no detected colour. |
| Location | Casefolded `[a-z0-9]+` token sets; Jaccard similarity; omitted if either is missing. |
| Date | `exp(-absolute_day_difference / 30)`; omitted if either date is missing/invalid. |
| Missing structured features | Omit unavailable signals and renormalize the weights of available signals. |
| Final score | Weighted mean scaled to 0–100 and rounded to two decimals. It is a similarity score, not a probability. |
| Notification cutoff | Effective Django setting 35.0; notifications are eligible at score >= 35. |
| Suggestions top-K | API default 10, validates 1–50; frontend requests 10. No score threshold is applied by the suggestions endpoint. |

## Reproduction

From the project root, using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m ml.evaluate_model
.\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v
```

The evaluation script loads the effective notification cutoff from Django
settings (which may be overridden by the local environment), reads the fixed
CSV, and regenerates `evaluation_results.json` and `evaluation_results.csv`.
It does not connect to a database or access report/user data. The dataset hash,
effective cutoff, full configuration, aggregate metrics, and pair-level results
are recorded in the JSON file.
