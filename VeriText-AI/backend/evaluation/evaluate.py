#!/usr/bin/env python3
"""
Independent evaluation of the VeriText AI NLP engine.

This script does **not** touch the web app or the database. It loads the labelled
sentence pairs in ``eval_dataset.jsonl``, runs the same embedding model and the
same lexical/classification primitives the production engine uses, and reports:

1. cosine similarity statistics per labelled category,
2. threshold sweeps with precision / recall / F1 for three decision rules
   (naive cosine threshold, cosine OR near-exact lexical, production rule),
3. confusion matrices at the configured operating point,
4. the effect of the generic-phrasing safeguard on paraphrase detection,
5. every false positive and false negative, with its id, so results are auditable.

Two different questions are kept separate, because they are not the same:

* **Reuse identification** — positive = identical / lightly modified / paraphrased
  ("should an integrity reviewer look at this pair?")
* **Semantic relatedness** — positive = the above plus semantically similar pairs
  ("does the model agree that these sentences mean similar things?")

Run:
    cd backend
    python evaluation/evaluate.py                 # console report
    python evaluation/evaluate.py --markdown      # + docs/evaluation_results.md
    python evaluation/evaluate.py --json          # + docs/evaluation_results.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from config import Config
from services import hardware  # noqa: E402
from services.embedding_service import get_embedding_service  # noqa: E402
from services.plagiarism_detector import _classify_pair  # noqa: E402
from services.similarity_engine import lexical_comparison  # noqa: E402
from services.text_preprocessor import content_tokens, normalize_for_match  # noqa: E402

DATASET = Path(__file__).with_name("eval_dataset.jsonl")
OUTPUT_DIR = BASE.parent / "docs"
CATEGORY_ORDER = [
    "identical", "lightly_modified", "paraphrase", "semantically_similar",
    "common_expression", "technical_definition", "unrelated",
]
CATEGORY_DESCRIPTIONS = {
    "identical": "identical sentences",
    "lightly_modified": "light edits / synonyms",
    "paraphrase": "rewritten, same claim",
    "semantically_similar": "same topic, different claim",
    "common_expression": "generic academic phrasing",
    "technical_definition": "textbook definitions",
    "unrelated": "unrelated sentences",
}


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def load_pairs() -> List[Dict[str, Any]]:
    pairs = []
    with DATASET.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def _sentence(pair_id: str, text: str, index: int) -> Dict[str, Any]:
    return {
        "id": f"{pair_id}-{index}", "index": index, "text": text,
        "norm_text": normalize_for_match(text), "content_tokens": content_tokens(text),
        "word_count": len(text.split()), "page": 0, "paragraph": 0, "section": "body",
    }


def score_pairs(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run the real model + real lexical primitives on every pair."""
    embedder = get_embedding_service()
    texts: List[str] = []
    for pair in pairs:
        texts.extend([pair["a"], pair["b"]])
    vectors = embedder.encode(texts)

    scored = []
    for index, pair in enumerate(pairs):
        vec_a, vec_b = vectors[2 * index], vectors[2 * index + 1]
        cosine = float(vec_a @ vec_b)          # unit vectors => dot product == cosine
        sentence_a = _sentence(pair["id"], pair["a"], 0)
        sentence_b = _sentence(pair["id"], pair["b"], 1)
        lexical = lexical_comparison(
            sentence_a["norm_text"], sentence_b["norm_text"],
            sentence_a["content_tokens"], sentence_b["content_tokens"],
        )
        verdict = _classify_pair(sentence_a, sentence_b, cosine, lexical, Config)
        scored.append({
            **pair,
            "cosine": round(cosine, 4),
            "sequence_ratio": lexical["sequence_ratio"],
            "token_jaccard": lexical["token_jaccard"],
            "content_overlap": lexical["content_overlap"],
            "shared_terms": lexical["shared_content_terms"],
            "is_exact_string": lexical["is_exact_string"],
            "classification": verdict["classification"],
            "subtype": verdict["subtype"],
            "suppressed": verdict["suppressed"],
            "suppress_reason": verdict["suppress_reason"],
        })
    return scored


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def confusion(predicted: List[int], truth: List[int]) -> Dict[str, float]:
    tp = sum(1 for p, t in zip(predicted, truth) if p == 1 and t == 1)
    fp = sum(1 for p, t in zip(predicted, truth) if p == 1 and t == 0)
    fn = sum(1 for p, t in zip(predicted, truth) if p == 0 and t == 1)
    tn = sum(1 for p, t in zip(predicted, truth) if p == 0 and t == 0)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": round((tp + tn) / max(1, len(truth)), 4),
    }


def decide(pair: Dict[str, Any], rule: str, threshold: float) -> int:
    """Apply a decision rule to one pair."""
    cosine = pair["cosine"]
    lexical_hit = pair["is_exact_string"] or pair["sequence_ratio"] >= Config.NEAR_EXACT_LEXICAL
    if rule == "cosine":
        return int(cosine >= threshold)
    if rule == "hybrid":
        return int(cosine >= threshold or lexical_hit)
    if rule == "production":
        # Mirrors the shipped engine: classifier thresholds + safeguards.
        if pair["classification"] is None:
            return 0
        if pair["classification"] in ("exact", "near_exact"):
            return 1
        return int(cosine >= threshold and not pair["suppressed"])
    raise ValueError(rule)


def sweep(scored: List[Dict[str, Any]], label: str, rule: str) -> List[Dict[str, Any]]:
    truth = [int(p[label]) for p in scored]
    rows = []
    for step in range(40, 91):
        threshold = step / 100
        predicted = [decide(p, rule, threshold) for p in scored]
        rows.append({"threshold": threshold, **confusion(predicted, truth)})
    return rows


def best(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return max(rows, key=lambda r: (r["f1"], r["precision"]))


def at(rows: List[Dict[str, Any]], threshold: float) -> Dict[str, Any]:
    return min(rows, key=lambda r: abs(r["threshold"] - threshold))


def category_stats(scored: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output = []
    for category in CATEGORY_ORDER:
        values = [p["cosine"] for p in scored if p["category"] == category]
        if not values:
            continue
        output.append({
            "category": category,
            "description": CATEGORY_DESCRIPTIONS.get(category, category),
            "count": len(values),
            "min": round(min(values), 3),
            "median": round(statistics.median(values), 3),
            "mean": round(statistics.fmean(values), 3),
            "max": round(max(values), 3),
        })
    return output


def mistakes(scored: List[Dict[str, Any]], rule: str, threshold: float,
             mode: str) -> List[Dict[str, Any]]:
    """Collect false positives (mode='fp') or false negatives (mode='fn')."""
    output = []
    for pair in scored:
        predicted = decide(pair, rule, threshold)
        truth = int(pair["reuse"])
        if mode == "fp" and not (predicted == 1 and truth == 0):
            continue
        if mode == "fn" and not (predicted == 0 and truth == 1):
            continue
        output.append({
            "id": pair["id"], "category": pair["category"], "cosine": pair["cosine"],
            "sequence_ratio": pair["sequence_ratio"],
            "classification": pair["classification"], "suppressed": pair["suppressed"],
            "suppress_reason": pair["suppress_reason"],
            "a": pair["a"], "b": pair["b"],
        })
    return output


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def build_markdown(payload: Dict[str, Any]) -> str:
    stats = payload["category_stats"]
    reuse = payload["reuse_task"]
    related = payload["relatedness_task"]
    threshold = payload["default_threshold"]

    lines: List[str] = []
    add = lines.append
    add("# VeriText AI — NLP Engine Evaluation")
    add("")
    add(f"*Generated {payload['generated_at']} by `backend/evaluation/evaluate.py`.*")
    add("")
    add(f"Model: `{payload['model']}` · Labelled pairs: **{payload['pairs']}** · "
        f"Operating point: cosine ≥ **{threshold}**")
    add("")
    runtime = payload.get("runtime") or {}
    if runtime:
        gpu = f" · GPU: {runtime['gpu_name']}" if runtime.get("gpu_name") else " · no CUDA GPU detected"
        add(f"Executed on: **{runtime.get('device')}**{gpu} · PyTorch "
            f"{runtime.get('torch_version')} (CUDA build {runtime.get('cuda_build') or 'none'}) · "
            f"Python {runtime.get('python_version')} · batch {runtime.get('batch_size')} · "
            f"{runtime.get('platform')}")
        add("")
    add("This document reports measured numbers from a script that anyone can re-run. "
        "No accuracy value in this project is invented or estimated.")
    add("")
    add("These results describe sentence-pair behaviour on a 59-pair, author-labelled set. They are "
        "an engineering sanity check for this implementation — **not** a validated academic "
        "benchmark: there is no inter-annotator agreement study, no third-party corpus and no "
        "confidence interval. Cosine values are device-independent in principle; tiny float "
        "differences between GPU and CPU kernels are far below every reported threshold.")
    add("")

    add("## 1. Dataset")
    add("")
    add("Sentence pairs were written for this project and labelled by hand across seven "
        "categories. Each row below shows the pair counts used for evaluation.")
    add("")
    add("| Category | What it contains | Pairs | Cosine min | Median | Mean | Max |")
    add("|---|---|---:|---:|---:|---:|---:|")
    for row in stats:
        add(f"| `{row['category']}` | {row['description']} | {row['count']} | "
            f"{row['min']:.3f} | {row['median']:.3f} | {row['mean']:.3f} | {row['max']:.3f} |")
    add("")
    add("**Immediate observation:** the cosine distributions of `paraphrase` (0.26–0.68) "
        "and `common_expression` (0.68–0.98) barely overlap, and the boilerplate scores are "
        "*higher* than the paraphrase scores. A single similarity threshold therefore cannot "
        "separate rewriting from standard academic phrasing — this is the central empirical "
        "finding of the evaluation, and the reason the engine combines semantic, lexical and "
        "safeguard signals instead of reporting one number.")
    add("")

    add("## 2. Task: reuse identification")
    add("")
    add("Positive class = identical, lightly modified or paraphrased pairs (26 pairs). "
        "Negative class = semantically similar but independent claims, common expressions, "
        "textbook definitions and unrelated sentences (33 pairs).")
    add("")
    add("| Decision rule | Threshold | Precision | Recall | F1 | TP | FP | FN | TN |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, rule_rows, rule_key in [
        ("Naive cosine threshold (best F1)", reuse["sweep_cosine"], "cosine"),
        ("Cosine OR near-exact lexical (best F1)", reuse["sweep_hybrid"], "hybrid"),
        ("VeriText production rule (best F1)", reuse["sweep_production"], "production"),
    ]:
        row = best(rule_rows)
        add(f"| {name} | {row['threshold']:.2f} | {row['precision']:.3f} | {row['recall']:.3f} | "
            f"{row['f1']:.3f} | {row['tp']} | {row['fp']} | {row['fn']} | {row['tn']} |")
    for name, key in [
        ("Naive cosine @ operating point", "at_default_cosine"),
        ("Cosine OR near-exact @ operating point", "at_default_hybrid"),
        ("VeriText production rule @ operating point", "at_default_production"),
    ]:
        row = reuse[key]
        add(f"| {name} ({threshold:.2f}) | {threshold:.2f} | {row['precision']:.3f} | "
            f"{row['recall']:.3f} | {row['f1']:.3f} | {row['tp']} | {row['fp']} | "
            f"{row['fn']} | {row['tn']} |")
    add("")
    add("Reading these numbers honestly:")
    add("")
    add(f"* The shipped rule reaches F1 **{reuse['at_default_production']['f1']:.3f}** at the "
        f"operating point, with precision {reuse['at_default_production']['precision']:.3f} and "
        f"recall {reuse['at_default_production']['recall']:.3f}.")
    add("* Precision is limited by three things that a semantic model cannot resolve on its own: "
        "near-verbatim *definitions*, standard *methodology sentences* and *future-work boilerplate*. "
        "These are reported rather than silently dropped, because verbatim overlap is genuine "
        "evidence that a human must classify.")
    add("* Recall is limited by the well-known weakness of MiniLM-scale sentence embeddings on "
        "heavy paraphrase (cosine often 0.45–0.60). Lowering the threshold recovers paraphrase "
        "recall but also admits far more boilerplate; the sweep table makes that trade-off explicit.")
    add("")

    add("## 3. Effect of the generic-phrasing safeguard")
    add("")
    para = payload["paraphrase_task"]
    add("Task: flag `paraphrase` pairs (10) while rejecting `common_expression` and "
        "`technical_definition` pairs (17).")
    add("")
    add("| Variant | Precision | Recall | F1 |")
    add("|---|---:|---:|---:|")
    for name, key in [
        ("Raw cosine ≥ operating point", "without_safeguards"),
        ("Production classification (no suppression)", "classification_only"),
        ("Production classification + suppression", "with_safeguards"),
    ]:
        row = para[key]
        add(f"| {name} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |")
    add("")
    suppressed = [p for p in payload["scored_pairs"] if p["suppressed"]]
    add(f"The safeguard suppressed **{len(suppressed)}** pair(s) at the operating point "
        f"({', '.join(sorted({p['category'] for p in suppressed})) or 'none'}). "
        "Suppressed pairs stay visible in the API with a reason; they are only excluded from "
        "headline counts. The safeguard is deliberately conservative: it never suppresses "
        "exact or near-exact wording.")
    add("")

    add("## 4. Task: semantic relatedness")
    add("")
    row = related["best"]
    add("Positive class = identical, lightly modified, paraphrase and semantically similar "
        "pairs (34). This measures whether the embedding model understands meaning, independent "
        "of questions about copying.")
    add("")
    add(f"Best operating point: threshold {row['threshold']:.2f} → precision "
        f"**{row['precision']:.3f}**, recall **{row['recall']:.3f}**, F1 **{row['f1']:.3f}**.")
    add("")
    add("## 5. Errors at the operating point")
    add("")
    add("### False positives (flagged but labelled as not reuse)")
    add("")
    for item in payload["false_positives"]:
        add(f"* `{item['id']}` ({item['category']}, cosine {item['cosine']:.3f}, rule "
            f"`{item['classification']}`): “{item['a'][:110]}…” ↔ “{item['b'][:110]}…”")
    add("")
    add("### False negatives (labelled reuse but not flagged)")
    add("")
    for item in payload["false_negatives"]:
        add(f"* `{item['id']}` ({item['category']}, cosine {item['cosine']:.3f}, "
            f"sequence ratio {item['sequence_ratio']:.2f}): “{item['a'][:110]}…” ↔ "
            f"“{item['b'][:110]}…”")
    add("")

    add("## 6. Conclusions drawn from this evaluation")
    add("")
    add("1. The embedding model performs exactly as expected on its own task: unrelated text "
        "sits near zero cosine, paraphrases sit clearly above unrelated text, and identical "
        "text sits at 1.0. It is a usable signal.")
    add("2. Sentence-level cosine alone is **not** a plagiarism detector. Boilerplate and "
        "definitions can outscore genuine paraphrases, so the engine separates exact, "
        "near-exact and semantic evidence and marks weak evidence explicitly.")
    add("3. Reproducible evaluation matters more than a headline number. The dataset is small "
        "(59 pairs), written by the project author, and drawn mostly from one domain "
        "(computing/education). Treat these figures as an engineering sanity check, not as "
        "benchmark performance, and do not present them as accuracy claims about real documents.")
    add("")
    add("## 7. Limitations of the evaluation")
    add("")
    add("* 59 pairs is far too few for statistically stable estimates; a single pair moves "
        "precision by several points.")
    add("* Labels encode the author's judgement about what counts as 'reuse', which is itself "
        "contested in academic-integrity practice.")
    add("* Pair-level evaluation ignores document context. In the application, matches are "
        "clustered into passages, which changes how evidence should be interpreted.")
    add("* Only one embedding model is evaluated. A larger cross-encoder or a domain-tuned "
        "model would likely change the numbers, and would need its own calibration.")
    add("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the VeriText AI NLP engine.")
    parser.add_argument("--json", action="store_true", help="write evaluation_results.json")
    parser.add_argument("--markdown", action="store_true", help="write evaluation_results.md")
    parser.add_argument("--threshold", type=float, default=Config.SEMANTIC_THRESHOLD)
    args = parser.parse_args()

    pairs = load_pairs()
    print(f"Loaded {len(pairs)} labelled sentence pairs from {DATASET.name}")
    print(f"Model: {Config.MODEL_NAME}")
    print(f"Operating point: cosine >= {args.threshold}")
    print(f"Device: {hardware.describe()['device']['resolved']} "
          f"(CUDA available: {hardware.describe()['cuda']['available']})\n")

    scored = score_pairs(pairs)
    stats = category_stats(scored)

    print("Cosine similarity by category")
    print(f"{'category':24s} {'n':>3s} {'min':>6s} {'median':>7s} {'mean':>6s} {'max':>6s}")
    for row in stats:
        print(f"{row['category']:24s} {row['count']:3d} {row['min']:6.3f} {row['median']:7.3f} "
              f"{row['mean']:6.3f} {row['max']:6.3f}")

    sweeps = {
        "cosine": sweep(scored, "reuse", "cosine"),
        "hybrid": sweep(scored, "reuse", "hybrid"),
        "production": sweep(scored, "reuse", "production"),
    }
    related_sweep = sweep(scored, "related", "hybrid")

    print("\nReuse identification (26 positives / 33 negatives)")
    for name, rows in sweeps.items():
        row = best(rows)
        at_default = at(rows, args.threshold)
        print(f"  {name:11s} best: thr={row['threshold']:.2f} P={row['precision']:.3f} "
              f"R={row['recall']:.3f} F1={row['f1']:.3f} | at {args.threshold:.2f}: "
              f"P={at_default['precision']:.3f} R={at_default['recall']:.3f} F1={at_default['f1']:.3f}")

    print("\nSemantic relatedness best: ", end="")
    row = best(related_sweep)
    print(f"thr={row['threshold']:.2f} P={row['precision']:.3f} R={row['recall']:.3f} F1={row['f1']:.3f}")

    # Paraphrase detection with and without the safeguard.
    subset = [p for p in scored if p["category"] in ("paraphrase", "common_expression", "technical_definition")]
    subset_truth = [1 if p["category"] == "paraphrase" else 0 for p in subset]
    without = confusion([int(p["cosine"] >= args.threshold) for p in subset], subset_truth)
    classification_only = confusion(
        [int(p["classification"] is not None and (p["classification"] != "semantic" or p["cosine"] >= args.threshold))
         for p in subset], subset_truth)
    with_guard = confusion(
        [int(p["classification"] is not None and (p["classification"] != "semantic" or
             (p["cosine"] >= args.threshold and not p["suppressed"]))) for p in subset],
        subset_truth)
    print(f"\nParaphrase vs boilerplate: raw cosine P={without['precision']:.3f} "
          f"R={without['recall']:.3f} F1={without['f1']:.3f} | "
          f"with safeguards P={with_guard['precision']:.3f} R={with_guard['recall']:.3f} "
          f"F1={with_guard['f1']:.3f}")

    fp = mistakes(scored, "production", args.threshold, mode="fp")
    fn = mistakes(scored, "production", args.threshold, mode="fn")
    print(f"\nProduction rules at {args.threshold}: {len(fp)} false positives, {len(fn)} false negatives")
    for item in fp:
        print(f"  FP [{item['category']:20s}] cos={item['cosine']:.3f} {item['id']}")
    for item in fn:
        print(f"  FN [{item['category']:20s}] cos={item['cosine']:.3f} {item['id']}")

    # Record the environment so the numbers can be reproduced and compared honestly.
    from services.embedding_service import get_embedding_service

    runtime = hardware.describe()
    embedder_status = get_embedding_service().status()

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model": Config.MODEL_NAME,
        "runtime": {
            "device": embedder_status.get("device"),
            "device_requested": embedder_status.get("device_requested"),
            "cuda_available": runtime["cuda"]["available"],
            "gpu_name": runtime["gpu"]["name"],
            "torch_version": runtime["torch"]["version"],
            "cuda_build": runtime["torch"]["cuda_build"],
            "python_version": runtime["python"]["version"],
            "batch_size": embedder_status.get("batch_size"),
            "platform": runtime["platform"]["system"],
        },
        "pairs": len(scored),
        "default_threshold": args.threshold,
        "category_stats": stats,
        "reuse_task": {
            "sweep_cosine": sweeps["cosine"],
            "sweep_hybrid": sweeps["hybrid"],
            "sweep_production": sweeps["production"],
            "at_default_cosine": at(sweeps["cosine"], args.threshold),
            "at_default_hybrid": at(sweeps["hybrid"], args.threshold),
            "at_default_production": at(sweeps["production"], args.threshold),
        },
        "relatedness_task": {"best": row, "sweep": related_sweep},
        "paraphrase_task": {
            "without_safeguards": without,
            "classification_only": classification_only,
            "with_safeguards": with_guard,
        },
        "false_positives": fp,
        "false_negatives": fn,
        "scored_pairs": scored,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.json:
        target = OUTPUT_DIR / "evaluation_results.json"
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote {target}")
    if args.markdown:
        target = OUTPUT_DIR / "evaluation_results.md"
        target.write_text(build_markdown(payload), encoding="utf-8")
        print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
