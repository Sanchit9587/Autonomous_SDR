# Converse Agent — Classification Prompt (v1)

Used by `classifier.py`'s `LLMClassifier` for zero-shot reply classification.
Returns strict JSON: category (from a fixed set), sentiment, confidence.
The LLM classifies; the deterministic policy in `policy.py` decides the action.

## Intent
Bounded categories, temperature 0.0 for consistency, JSON-only output.
Low-confidence results are escalated to a human by the policy layer, not
guessed at.

## v2 note
Intended to be replaced by a trained scikit-learn classifier (TF-IDF + LR/SVM)
once labeled reply data is collected. The classify() interface stays identical.

## Change log
- v1 (initial): zero-shot LLM classification with keyword fallback.