# ArgMicrotexts inference profile: evidence and open decisions

Status: runnable English zero-shot profile. The no-`sameunit` segmentation
policy and 34-relation release-compatible inventory are fixed in version 1.
The multi-satellite evaluation normalization is implemented and documented;
aggregate metric computation remains to be implemented.

## Intended workflow

The immediate project starts from pre-segmented RS3 documents, exports only
their ordered EDU text to inference TSV, predicts one complete primary RST
tree, serializes that tree as RS3, and scores it against separately retained
gold RS3. Gold structure and relation labels must not enter target prompts.

## Local sources inspected

- `../rst_data/relation_inventories/argmicrotexts.tsv`: proposed exact
  35-entry machine-readable relation inventory.
- `../rst_data/relation_inventories/README.md`: inventory provenance and
  comparison with PCC `old` and `new` modes.
- `../rst_data/docs/relation_inventories/arg-microtexts/relation_inventory.txt`:
  exploratory inventory and `sameunit` notes.
- `../rst_data/original/arg-microtexts-multilayer/corpus/rst/`: 112 public
  English RST gold files from the multilayer corpus.
- `../rst_data/docs/guidelines/PCC/Stede 2016 - Handbuch Textannotation
  (PCC 2.0).pdf` and `Stede, Taboada & Das 2017 - Annotation Guidelines for
  Rhetorical Structure.pdf`: base annotation guidance.
- `../sfb_retreat_26/docs/Stede et al. 2016 - Parallel Discourse Annotations
  on a Corpus of Short Texts.pdf`: primary corpus paper.
- `../arg-microtexts/docs/DECISIONS.md`: English segmentation status and the
  decision to retain the main Same-Unit-affected segmentation as primary.
- `../sfb_retreat_26/rst-qud-comparison/multi_satellite_rule_comparison.md`:
  prior analysis of binarizing RS3 schemas with multiple satellites.

The ESSLLI segmentation notes and retreat paper-idea notes were also searched.
They motivate possible future re-segmentation and attribution work, but do not
currently constitute an operational RST annotation guideline.

## Exact inventory evidence

Stede et al. (2016) say that the RST layer was annotated according to the PCC
guidelines and that some definitions were adjusted for argumentative text.
They do not enumerate a Microtexts relation inventory or state that a fixed
PCC inventory was extended by a particular list. The inventory below is
therefore release-compatibility evidence from the RS3 headers, not a label list
reported in the paper.

The proposed ArgMicrotexts inventory has 28 `rst` and 7 `multinuc` entries.
Relative to the repository's current PCC starter profile, it:

- removes `attribution`, `reason-n`, and multinuclear `same-unit`;
- adds mononuclear `sameunit`, plus `disjunction`, `restatement-mn`,
  `unconditional`, and `unstated-relation`;
- retains `solutionhood` but not the newer PCC corpus label `solutionhood-N`.

The original ArgMicrotexts files declare 34 relations in 103 documents. Nine
documents additionally declare mononuclear `sameunit`. This unusual typing is
retained for source compatibility: in these files, `sameunit` is serialized as
a directed relation from an interrupted fragment to its resumed host node or
span. The paper calls Same-Unit artificial and says it was introduced only to
repair RST trees after embedded EDUs were split off for cross-layer
compatibility. It does not justify the RS3 `rst` type as a theoretical claim.

The maintained PCC guideline-core inventory has 31 entries, not 32. The
34-entry Microtexts header without `sameunit` differs from that inventory by
omitting `reason-N` and adding `disjunction`, `restatement-mn`,
`unconditional`, and `unstated-relation`. Reducing this header to labels found
on the 112 gold trees would be corpus-observation-based; preserving the header
does not make that reduction.

## Corpus audit on 2026-09-10

The 112 main English gold RS3 files contain:

- 680 segments and 514 groups;
- exactly one root in every document;
- 27 documents whose segment IDs are not consecutive textual positions;
- 568 segments with leading or trailing boundary whitespace in the RS3 text;
- 10 `sameunit` edges across nine documents;
- 41 documents in which more than one mononuclear satellite attaches directly
  to the same nucleus.

Relations observed on source tree edges were:

```text
antithesis 32       background 18       cause 20
circumstance 7      concession 65       condition 21
conjunction 88      contrast 6          disjunction 6
e-elaboration 9     elaboration 28       evaluation-n 1
evaluation-s 2      evidence 13          interpretation 4
joint 34            justify 7            list 107
means 2             motivation 3         preparation 3
purpose 4           reason 181           restatement 5
result 3            sameunit 10          solutionhood 1
unless 2
```

The declared labels `enablement`, `otherwise`, `summary`, `unconditional`,
`unstated-relation`, and `restatement-mn` are unused in these 112 primary
trees. Header membership alone therefore does not establish corpus-specific
decision rules or useful demonstrations for them.

## Preprocessing decision

`src.rs3_to_e2e_tsv` reads segment elements in XML body order, assigns fresh
indices `1..N`, and preserves text exactly. A sidecar manifest maps the fresh
indices to source node IDs and records hashes. This is required because RS3
node IDs are graph identifiers rather than textual offsets.

The exporter successfully processed all 112 public trees and all 680 EDUs.
After boundary-whitespace stripping, the extracted sequence independently
matched the maintained English `multilayer_gold/*.edus` exports for all 112
documents.

## Current English pilot batch

`data/input/microtexts_nosameunit_subset/` contains 14 English RS3 files. They
are byte-identical copies of the corresponding public multilayer-corpus gold
files, so they are a gold pilot/evaluation batch rather than unseen private
inference data. The batch contains 79 EDUs, with 4--9 EDUs per document. All
files declare the same 34-entry inventory, and none declares or uses
`sameunit`. `src.rs3_to_e2e_tsv` converts all 14 successfully.

For this project, English is the only inference language. The supplied
segmentation never represents an interrupted EDU using `sameunit`, so the
project prompt and scheme should omit `sameunit` on the basis of that declared
segmentation policy, not because the relation happens to be absent from these
14 gold trees.

## Evaluation normalization decision

RST-Tace parsed a simple source document (`micro_b001`) but rejected tested
multi-satellite documents (`micro_b022` and `micro_b045`) with `Multiple mono
nuclear relations for single element`. This affects many source files and must
not be mistaken for a preprocessing or XML-validity failure.

The project adopts the author's existing deterministic normalizer from
`sfb_retreat_26/rst-qud-comparison/normalize_rs3.py`, imported from Git commit
`aeff129def1cde9aa94655be772c9da8432a963a`. It attaches left satellites nearest
to farthest, then right satellites nearest to farthest, inserting only the
span groups required for binary mononuclear structure. The algorithm preserves
EDU text/order, relation labels, nuclearity, existing IDs, and relation-header
declarations. See `docs/rs3-normalization.md`.

Strict normalization succeeded for all 14 pilot documents and all 112 public
English ArgMicrotexts documents. Thirty-nine of the 112 documents required 44
derived span groups. Gold and predictions are normalized independently with
the same function; original files remain unchanged. Normalization must never
relabel or otherwise correct a prediction before scoring.

The normalizer intentionally leaves n-ary multinuclear cores unchanged. None
of the 14 pilot documents has a multinuclear core wider than two, so the pilot
requires no additional convention. Thirteen documents in the full 112-file
corpus each contain one three-nucleus `list`; full-corpus evaluation must state
whether those are evaluated natively or deterministically binarized.

## Version 1 prompt decisions

`configs/schemes/argmicrotexts.yaml` and
`prompts/ICL_argmicrotexts_algo_e2e.txt` define version 1 as follows:

- use all 34 relations declared in the no-`sameunit` release header rather than
  reducing the space from observed gold edges;
- omit `sameunit`, `attribution`, and `reason-N`;
- keep the six header-only unused labels available; define
  `unstated-relation` as a strict last resort rather than an uncertainty label;
- use English-only instructions and a zero-shot document setup with one
  syntax-only compact-tree example, but no gold input/output demonstration;
- test exact prompt/profile label and relation-type agreement.

Aggregate metric definitions and output format remain to be implemented. Any
future few-shot experiment must also define a held-out split before selecting
worked corpus examples.
