# RST Website / Classical RST Native Prompt: Relation Labeling

You are annotating discourse relations according to the **classical Rhetorical Structure Theory website formulation**, using the extended relation definitions.

## Task
Given two pre-segmented spans, identify the best classical RST relation holding between them. Use only the relation names listed below. Assume the spans have already been selected; do not split, merge, or reorder them.

You will receive:
- `left`: first span
- `right`: second span
- optional `context_before`
- optional `context_after`

Return one JSON object only.

## Classical RST principles
RST explains text coherence by assigning each part of a coherent text a plausible role. Relations are observations made by an analyst/observer about what it is plausible that the author intended the reader to recognize. A relation is not just a semantic connection between clauses; it includes an **intended reader effect**.

For a mononuclear relation, one span is more central to the author’s purposes: this span is the **nucleus** (`N`). The other span is the **satellite** (`S`). For a multinuclear relation, no span is more central; both are nuclei.

When choosing a relation, test whether the following definition components are satisfied:
- constraints on `N`, if any;
- constraints on `S`, if any;
- constraints on the `N + S` combination;
- the intended effect on the reader.

The classical RST relation inventory is theoretically open, but for this task you must choose only from the inventory below. If no label fits well, use `Joint` for a weak equal-weight connection or mark low confidence; do not invent a new label.

## Native classical RST relation inventory

### Mononuclear relations
Use these with `NS` or `SN` nuclearity.

- `Antithesis`: `N` and `S` are in contrast. The author has positive regard for `N` and disfavours or rejects `S`. Recognizing the contrast and incompatibility increases the reader’s positive regard for `N`.
- `Background`: `S` provides information that helps the reader sufficiently understand `N`. Use when `S` supplies general knowledge, setting, or explanatory background needed for comprehension.
- `Circumstance`: `S` provides an interpretive framework, situation, time, place, or condition within which the reader should interpret `N`. Use when `S` frames the occurrence or interpretation of `N`, rather than merely explaining it.
- `Concession`: The author acknowledges or accepts `S`, even though `S` is apparently incompatible with `N`. Recognizing that `N` still holds despite `S` increases the reader’s positive regard for `N`.
- `Condition`: `S` presents a hypothetical, future, or otherwise unrealized situation; realization of `N` depends on realization of `S`.
- `Elaboration`: `S` gives additional detail about `N` or an element of `N`. Typical subtypes include set-member, abstraction-instance, whole-part, process-step, object-attribute, and general-specific detail.
- `Enablement`: `S` increases the reader’s potential ability to perform the action in `N`.
- `Evaluation`: `S` expresses an evaluative assessment of `N`; the intended effect is that the reader recognizes the assessment.
- `Evidence`: The reader may not already believe `N` strongly enough; `S` is intended to increase the reader’s belief in `N`.
- `Interpretation`: `S` interprets, explains the significance of, or relates the situation in `N` to a framework of ideas not already explicit in `N`.
- `Justify`: `S` increases the reader’s readiness to accept the writer’s right, basis, or authority to present `N`. Use for justification of saying/asserting, not primarily for proof that `N` is true.
- `Motivation`: `S` increases the reader’s desire or willingness to perform the action in `N`.
- `Non-volitional Cause`: `S` is a non-deliberate cause of the situation in `N`; no intentional agent’s decision is central.
- `Non-volitional Result`: `S` is a non-deliberate result caused by the situation in `N`.
- `Otherwise`: `S` presents an unrealized situation; realization of `N` depends on non-realization of `S`. This is a negative condition: if `S` happens, `N` will not happen or hold.
- `Purpose`: `S` presents the intended situation or goal to be realized through the activity in `N`.
- `Restatement`: `S` re-expresses `N` in different words, with roughly comparable scope or bulk.
- `Solutionhood`: `S` presents a problem, question, request, need, or other situation requiring resolution; `N` provides or contributes to a solution.
- `Summary`: `S` gives a shorter restatement or condensation of `N`.
- `Volitional Cause`: `S` presents a situation that causes or motivates an intentional action in `N`; an intentional agent’s decision is central.
- `Volitional Result`: `S` presents an intentional action or situation that results from `N`; an intentional agent’s response is central.
- `Preparation`: `S` makes the reader more ready, interested, or able to read and interpret `N`. Use when `S` prepares expectations rather than supplying substantive background information.

### Multinuclear relations
Use these only with `NN` nuclearity.

- `Contrast`: The spans are comparable alternatives or situations, and one or more comparable differences are highlighted without one span being more central.
- `Joint`: The spans are connected without a more specific relation and without a nuclearity imbalance.
- `List`: The spans are comparable items in a list or set.
- `Sequence`: The spans describe events or steps ordered in time or procedural order.

## Nuclearity conventions
Use:
- `NS` if left is nucleus and right is satellite.
- `SN` if left is satellite and right is nucleus.
- `NN` for multinuclear relations.
- `unknown` only if nuclearity cannot be inferred.

## Decision procedure
1. Decide whether one span is more central to the author’s purposes. If not, use a multinuclear relation.
2. For mononuclear relations, identify `N` and `S` before choosing the label.
3. Test the relation’s intended reader effect, not only the semantic connection.
4. Prefer the relation whose definition best explains why both spans are present.
5. If multiple analyses are plausible, choose the most locally supported one and mention the rejected alternative.

## Common distinction checks
- `Evidence` vs. `Justify`: `Evidence` supports belief in the truth of `N`; `Justify` supports the writer’s right, authority, or basis to assert `N`.
- `Antithesis` vs. `Concession` vs. `Contrast`: `Antithesis` rejects/disfavours `S` and favors `N`; `Concession` accepts `S` but maintains `N`; `Contrast` is equal-weight difference.
- `Background` vs. `Circumstance`: `Background` helps the reader understand `N`; `Circumstance` supplies the situation or framework within which `N` should be interpreted.
- `Cause` vs. `Result`: in Cause, `S` causes `N`; in Result, `S` results from `N`.
- `Volitional` vs. `Non-volitional`: use `Volitional` when an intentional agent’s decision or action is central; otherwise use `Non-volitional`.
- `Restatement` vs. `Summary`: `Restatement` is comparable in scope; `Summary` is shorter and more condensed.
- `Preparation` vs. `Background`: `Preparation` readies the reader for `N`; `Background` supplies substantive knowledge needed to understand `N`.

## Output format
Return only valid JSON:

```json
{
  "native_label": "one allowed classical RST label",
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
