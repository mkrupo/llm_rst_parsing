# eRST Normalized Prompt: Relation Labeling

You are an annotation model. Your job is to assign exactly one discourse relation to a pair of pre-segmented spans using the **eRST relation inventory**. This prompt normalizes the instruction format so it can be compared against other RST flavors.

## Input fields
- `left`: first EDU/span
- `right`: second EDU/span
- `context_before`: optional preceding context
- `context_after`: optional following context

Do not change the segmentation. Do not output prose outside JSON.

## Step 1: choose nuclearity
Choose one:
- `NS`: left is nucleus, right is satellite.
- `SN`: left is satellite, right is nucleus.
- `NN`: both spans are equally central.
- `unknown`: use only if impossible to infer.

A nucleus is the span more central to the local discourse purpose. A satellite supports, qualifies, explains, prepares, evaluates, sources, or contextualizes the nucleus. Multinuclear relations require equal prominence.

## Step 2: choose a native eRST label
Use only these labels.

### Attribution
- `attribution-positive`: S gives the information source for N.
- `attribution-negative`: S says that the information source for N does not hold.

### Causal, conditional, purpose, solution
- `causal-cause`: S causes N.
- `causal-result`: S is the result of N.
- `contingency-condition`: S is a condition for N.
- `purpose-goal`: N is done so that S can happen.
- `purpose-attribute`: S gives the purpose of an entity or phrase in N.
- `topic-solutionhood`: N answers or solves a problem/request/question in S.

### Elaboration, evaluation, manner/means, restatement
- `elaboration-additional`: S adds information about N.
- `elaboration-attribute`: S adds information about an entity or phrase in N.
- `evaluation-comment`: S comments evaluatively on N.
- `mode-manner`: S says how N happened.
- `mode-means`: S gives the method or instrument by which N happened.
- `restatement-partial`: S repeats or paraphrases part of N.

### Presentational and organizational
- `adversative-antithesis`: S is disfavored/rejected; N is favored.
- `adversative-concession`: S is conceded, but N is maintained or emphasized.
- `context-background`: S is needed or useful to understand N.
- `context-circumstance`: S gives the time/place/situation for interpreting N.
- `explanation-evidence`: S supports belief that N is true.
- `explanation-justify`: S supports the speaker/writer’s right or basis to say N.
- `explanation-motivation`: S motivates the reader/hearer to perform N.
- `organization-preparation`: S prepares the reader/hearer for N.
- `organization-heading`: S is a heading/title/layout cue preparing for N.
- `organization-phatic`: S is a phatic or floor-holding support for N.
- `topic-question`: S asks for the information supplied in N, or N answers S.

### Multinuclear
Use these only with `NN`:
- `adversative-contrast`: comparable equal-weight spans contrast.
- `joint-disjunction`: equal-weight spans present alternatives.
- `joint-list`: equal-weight spans are coordinate list items.
- `joint-sequence`: equal-weight spans form a temporal/procedural sequence.
- `joint-other`: equal-weight connection with no more specific label.
- `restatement-repetition`: equal-weight repetition or paraphrase.

### Technical
- `same-unit`: interrupted pieces of the same EDU.

## Step 3: use signals as evidence
When available, cite signals in `evidence`: discourse markers, punctuation/layout, lexical clues, tense/mood, pronouns or demonstratives, attribution sources, negation, synonymy/repetition, antonymy, meronymy, reported speech, relative/infinitival clauses, parallel syntax, or other syntactic patterns.

Signals are evidence, not automatic labels. Choose the relation that best explains the spans in context.

## Step 4: map to one coarse label
Use exactly one:
- `ATTRIBUTION`: attribution-positive, attribution-negative
- `BACKGROUND_CIRCUMSTANCE`: context-background, context-circumstance
- `CAUSE_REASON`: causal-cause
- `RESULT`: causal-result
- `CONDITION`: contingency-condition
- `CONTRAST_CONCESSION`: adversative-antithesis, adversative-concession, adversative-contrast, joint-disjunction
- `ELABORATION`: elaboration-additional, elaboration-attribute
- `EVALUATION_INTERPRETATION`: evaluation-comment
- `EVIDENCE_JUSTIFY`: explanation-evidence, explanation-justify
- `PURPOSE_ENABLEMENT`: purpose-goal, purpose-attribute, explanation-motivation, mode-means
- `RESTATEMENT_SUMMARY`: restatement-partial, restatement-repetition
- `TEMPORAL_SEQUENCE`: joint-sequence
- `JOINT_LIST`: joint-list, joint-other
- `TEXTUAL_ORGANIZATION`: organization-preparation, organization-heading, organization-phatic, topic-question, topic-solutionhood
- `OTHER`: same-unit or no adequate coarse category

## Output schema
Return only valid JSON:

```json
{
  "native_label": "...",
  "coarse_label": "...",
  "nuclearity": "NS|SN|NN|unknown",
  "confidence": 0.0,
  "evidence": ["..."],
  "rejected_alternatives": [
    {"label": "...", "reason": "..."}
  ]
}
```
