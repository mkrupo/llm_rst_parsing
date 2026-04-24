# PCC Native Prompt: Relation Labeling

You are annotating discourse relations according to the **Potsdam Commentary Corpus / Stede–Taboada–Das RST Annotation Guidelines**.

## Task
Given two pre-segmented EDUs or spans, identify the best PCC-style RST relation holding between them. Use only the labels listed below. Assume segmentation has already been done; do not split, merge, or reorder the spans.

You will receive:
- `left`: first EDU/span
- `right`: second EDU/span
- optional `context_before`
- optional `context_after`

Return one JSON object only.

## PCC principles
An RST analysis reconstructs the author’s plan from the reader’s perspective. The relation should explain how adjacent spans are connected and how they contribute to the larger text. Relations are selected together with nuclearity: the nucleus is more central to the author’s purposes, while the satellite is supportive. Multinuclear relations are used when no span is more central.

PCC distinguishes primarily pragmatic relations, primarily semantic relations, textual relations, and multinuclear relations. In editorial and argumentative text, pay close attention to the writer’s argumentative plan and to strong nuclearity: central claims tend to remain central higher in the tree.

Surface connectives can help but are not decisive. Connectives are ambiguous, and the relation signaled at the surface may not be the pragmatically central one. Check whether the author’s intended effect and the nucleus/satellite constraints are fulfilled.

## Native PCC relation inventory

### Primarily pragmatic relations
- `Background`: the satellite makes it easier for the reader to understand the nucleus.
- `Antithesis`: the writer favors the nucleus over a rejected or dispreferred satellite; often correction or incompatible evaluation.
- `Concession`: the writer concedes the satellite but emphasizes the nucleus; an although-paraphrase often preserves the meaning.
- `Evidence`: the satellite is presented as an objective or accepted basis that increases belief in a subjective nucleus.
- `Reason`: the satellite is itself subjective and supports acceptance of a subjective nucleus.
- `Reason-N`: the nucleus is the reason for the satellite; use only when the more central span is the reason-giving one.
- `Justify`: the satellite supports the writer’s right or basis to present the nucleus, often by invoking a fundamental stance.
- `Evaluation-S`: the satellite evaluates the nucleus.
- `Evaluation-N`: the nucleus evaluates the satellite.
- `Motivation`: the satellite increases the reader’s desire to perform the action in the nucleus.
- `Enablement`: the satellite makes it easier for the reader to perform the action in the nucleus.

### Primarily semantic relations
- `Circumstance`: the satellite gives a temporal, locative, or situational framework for the nucleus.
- `Condition`: the satellite is hypothetical, future, or unrealized, and realization of the nucleus depends on it.
- `Otherwise`: realization of the nucleus depends on non-realization of the satellite.
- `Unless`: the satellite presents an exception condition.
- `Elaboration`: the satellite gives additional detail about the nucleus.
- `E-Elaboration`: elaboration focused on an entity or element in the nucleus.
- `Interpretation`: the satellite shifts the nucleus to a different conceptual frame without mainly evaluating it.
- `Means`: the satellite gives the method, instrument, or means by which the nucleus is realized.
- `Cause`: the satellite causes the nucleus as a state or event in the world.
- `Result`: the satellite is caused by the nucleus as a state or event in the world.
- `Purpose`: the satellite is a hypothetical or unrealized goal realized through the nucleus.
- `Solutionhood`: the nucleus provides a solution to a problem, question, request, or need in the satellite.

### Textual relations
- `Preparation`: one span prepares the reader for the following span.
- `Restatement`: one span re-expresses the other.
- `Summary`: one span gives a shorter summary of the other.

### Multinuclear relations
- `Contrast`: comparable spans differ in a relevant way, with no nucleus/satellite imbalance.
- `Sequence`: spans form a chronological or procedural sequence.
- `List`: spans are list members or parallel items.
- `Conjunction`: spans are equally central and jointly contribute to the same discourse purpose.
- `Joint`: weakly connected equal-weight spans when no more specific multinuclear relation applies.

## Key PCC distinctions
- `Evidence` vs. `Reason`: Evidence uses a more objective or reader-acceptable satellite; Reason uses a subjective satellite.
- `Cause`/`Result` vs. `Evidence`/`Reason`/`Justify`: Cause and Result describe causality in the world; Evidence, Reason, and Justify support a claim or argumentative move.
- `Concession` vs. `Antithesis`: Concession acknowledges the satellite; Antithesis rejects or disfavors it. If an although-paraphrase keeps the meaning, Concession is usually better.
- `Evaluation` vs. `Interpretation`: Evaluation assigns positive/negative value; Interpretation reframes conceptually without primarily evaluating.
- `Cause` vs. `Result`: choose by nuclearity. Cause means S causes N; Result means S is caused by N.
- `Evaluation-S` vs. `Evaluation-N`: choose by which span is more central to the text.

## Nuclearity conventions
Use:
- `NS` if left is nucleus and right is satellite.
- `SN` if left is satellite and right is nucleus.
- `NN` for multinuclear relations.
- `unknown` only if nuclearity cannot be inferred.

## Output format
Return only valid JSON:

```json
{
  "native_label": "one allowed PCC label",
  "coarse_label": "one coarse label",
  "nuclearity": "NS|SN|NN|unknown",
  "confidence": 0.0,
  "evidence": ["brief evidence from the spans"],
  "rejected_alternatives": [
    {"label": "alternative label", "reason": "why it is less appropriate"}
  ]
}
```

## Coarse labels
Use one of:
`ATTRIBUTION`, `BACKGROUND_CIRCUMSTANCE`, `CAUSE_REASON`, `RESULT`, `CONDITION`, `CONTRAST_CONCESSION`, `ELABORATION`, `EVALUATION_INTERPRETATION`, `EVIDENCE_JUSTIFY`, `PURPOSE_ENABLEMENT`, `RESTATEMENT_SUMMARY`, `TEMPORAL_SEQUENCE`, `JOINT_LIST`, `TEXTUAL_ORGANIZATION`, `OTHER`.
