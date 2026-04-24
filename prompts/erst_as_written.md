# eRST Native Prompt: Relation Labeling

You are annotating discourse relations according to **Enhanced Rhetorical Structure Theory (eRST)**.

## Task
Given two pre-segmented discourse units or spans, identify the best eRST relation holding between them. Use only the labels listed below. Assume segmentation has already been done; do not split, merge, or reorder the spans.

You will receive:
- `left`: first EDU/span
- `right`: second EDU/span
- optional `context_before`
- optional `context_after`

Return one JSON object only.

## eRST principles
In eRST, EDUs roughly correspond to propositions, clauses, or sentences. Relations connect EDUs or larger spans into an RST-style discourse structure. If one span is more prominent or more central to the local discourse purpose, it is the **nucleus** and the other is the **satellite**. If the participating spans are equally prominent, use a **multinuclear** relation.

Prefer relations that explain the rhetorical purpose of one unit with respect to the other. Use surface and structural evidence where available. eRST treats signals as important evidence: discourse markers, graphical layout, lexical cues, morphology, numerical organization, reference, semantic relations, syntactic constructions, and reported-speech structures can all signal relations.

## Native eRST label inventory

### Subject-matter / informational relations
- `attribution-positive`: one span provides the source of information in the other.
- `attribution-negative`: one span denies or negates the source of information in the other.
- `causal-cause`: the satellite/event causes the nucleus/event.
- `contingency-condition`: one span gives a condition for the other.
- `elaboration-additional`: one span provides additional information about the other.
- `elaboration-attribute`: one span provides information about a phrase or entity inside the other.
- `evaluation-comment`: one span gives an evaluative comment or opinion about the other.
- `mode-manner`: one span describes how the other happened.
- `mode-means`: one span gives the means or instrument by which the other happened.
- `purpose-goal`: the nucleus occurs in order for the satellite goal to happen.
- `purpose-attribute`: one span gives the purpose of a phrase or entity in the other.
- `restatement-partial`: one span reiterates part, but not all, of the other.
- `causal-result`: one span presents the result of the other.
- `topic-solutionhood`: one span gives a solution or answer to a problem in the other.

### Presentational relations
- `adversative-antithesis`: the writer/speaker favors the nucleus over a rejected or dispreferred alternative.
- `context-background`: the satellite gives information needed to understand the nucleus.
- `context-circumstance`: the satellite gives temporal, spatial, or situational circumstances for interpreting the nucleus.
- `adversative-concession`: the writer/speaker admits the satellite but maintains or emphasizes the nucleus.
- `explanation-evidence`: the satellite gives evidence that the nucleus is true or credible.
- `explanation-justify`: the satellite justifies the writer/speaker’s right or basis for saying the nucleus.
- `explanation-motivation`: the satellite motivates the reader/hearer to perform the action in the nucleus.
- `organization-preparation`: one span prepares the reader/hearer for the other.
- `organization-heading`: a heading, title, or layout element prepares for the following content.
- `organization-phatic`: a phatic or floor-holding expression supports the following discourse without much semantic content.
- `topic-question`: one span asks for information supplied by the other.

### Multinuclear relations
- `adversative-contrast`: similar or comparable spans are presented with a contrast.
- `joint-disjunction`: spans present alternatives.
- `joint-list`: spans are coordinate, parallel, or list-like.
- `joint-sequence`: spans form a chronological or procedural sequence.
- `joint-other`: spans are equal in prominence but do not fit a more specific multinuclear relation.
- `restatement-repetition`: spans restate the same content symmetrically or nearly symmetrically.

### Technical label
- `same-unit`: use only when the two spans are interrupted pieces of the same EDU.

## Evidence and signals to consider
Look for signals, but do not rely mechanically on them:
- discourse markers: because, so, although, but, and, then, or
- graphical signals: colon, dash, semicolon, headings, list numbering, question marks, parentheses, quotation marks
- lexical signals: evaluative words, alternate expressions, indicative phrases
- morphological signals: mood or tense
- reference: demonstratives, pronouns, propositional anaphora, comparative reference
- semantic signals: antonymy, attribution source, lexical chains, meronymy, negation, repetition, synonymy
- syntactic signals: causal excess, infinitival/relative clauses, reported speech, subject-auxiliary inversion, parallel syntax, modifiers

## Nuclearity conventions
Use:
- `NS` if left is nucleus and right is satellite.
- `SN` if left is satellite and right is nucleus.
- `NN` for multinuclear relations.
- `unknown` only if nuclearity cannot be inferred.

For mononuclear labels, choose the direction that matches the definition. For multinuclear labels, use `NN`.

## Output format
Return only valid JSON:

```json
{
  "native_label": "one allowed eRST label",
  "coarse_label": "one coarse label",
  "nuclearity": "NS|SN|NN|unknown",
  "confidence": 0.0,
  "evidence": ["brief evidence or signal from the spans"],
  "rejected_alternatives": [
    {"label": "alternative label", "reason": "why it is less appropriate"}
  ]
}
```

## Coarse labels
Use one of:
`ATTRIBUTION`, `BACKGROUND_CIRCUMSTANCE`, `CAUSE_REASON`, `RESULT`, `CONDITION`, `CONTRAST_CONCESSION`, `ELABORATION`, `EVALUATION_INTERPRETATION`, `EVIDENCE_JUSTIFY`, `PURPOSE_ENABLEMENT`, `RESTATEMENT_SUMMARY`, `TEMPORAL_SEQUENCE`, `JOINT_LIST`, `TEXTUAL_ORGANIZATION`, `OTHER`.
