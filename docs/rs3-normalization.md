# RS3 structural normalization for evaluation

RS3 can represent one nucleus with several satellites as one flat schema. The
compact prediction format and RST-Tace use binary mononuclear attachments.
Therefore, two equivalent analyses can have different RS3 grouping nodes and
cannot be compared reliably until the implicit attachments have one documented
representation.

The implementation in `src/normalize_rs3.py` was imported from the author's
`sfb_retreat_26/rst-qud-comparison/normalize_rs3.py` at Git commit
`aeff129def1cde9aa94655be772c9da8432a963a`. Its normalization algorithm is
unchanged. This repository adds file/directory input support, refuses to
overwrite derived files unless explicitly requested, forbids input and output
identity, and validates a whole batch before writing any of it.

## What normalization does and does not do

Normalization may insert anonymous `span` groups so that no structural node
has more than one mononuclear satellite. It preserves:

- every EDU and its exact text;
- EDU order;
- every annotated relation label;
- the nucleus/satellite direction of every relation;
- every existing node ID; and
- the relation declarations in the RS3 header.

It does **not** relabel a model decision, repair a wrong tree, or make a
prediction more similar to gold. Original gold and prediction files remain
unchanged. Both are normalized independently into derived evaluation files by
the same deterministic function. A difference such as gold `reason` versus
predicted `evidence` remains a relation error after normalization.

## Deterministic attachment rule

Starting with the annotated nucleus subtree:

1. attach preceding (left) satellites from nearest to farthest;
2. attach succeeding (right) satellites from nearest to farthest; and
3. after each attachment, treat the resulting span as the nucleus for the next
   attachment.

For a flat `S-N-S-S` schema:

```text
Source order:             S-left   N   S-right-1   S-right-2
First attachment:              (S-left  N)
Second attachment:             ((S-left  N)  S-right-1)
Normalized structure:          (((S-left  N)  S-right-1)  S-right-2)
```

This is an inside-to-outside convention, not an attempt to recover extra human
decisions that the flat RS3 source never recorded. Introduced intermediate
constituents are consequences of this declared convention and must be
described when reporting constituent-based metrics.

The normalizer does not binarize a multinuclear core with three or more nuclei.
That is a separate representation decision. None of the 14 current pilot files
contains such a group, so it does not affect the pilot evaluation. Thirteen of
the 112 public English files do contain one three-nucleus `list` group and will
need a documented multinuclear policy before scaling evaluation to that full
corpus. The other repository's parenthetical converter left-binarizes these
cores; that behavior has not silently been folded into this normalizer.

## Validation behavior

Strict mode is the default. It rejects malformed XML, duplicate or dangling
IDs, cycles, empty segments, multiple substantive roots, non-projective child
ordering, malformed span or multinuclear groups, heterogeneous multinuclear
cores, undeclared relations, and relation-type misuse.

`--compatibility` only permits legacy relation-header mismatches. It does not
weaken structural validation and does not change labels. It should not be used
for the current ArgMicrotexts experiment because all 112 public source files
pass strict mode.

## Commands

Normalize one file:

```bash
python -m src.normalize_rs3 \
  data/input/microtexts_nosameunit_subset/micro_b001_original.rs3 \
  results/normalized/gold/micro_b001_original.rs3
```

Normalize a flat directory:

```bash
python -m src.normalize_rs3 \
  data/input/microtexts_nosameunit_subset \
  results/normalized/gold
```

The command refuses existing outputs by default. `--overwrite` is available
only for deliberately replacing derived output; it can never overwrite an
input in place.

## Verification

On 2026-09-10, strict in-memory normalization succeeded for all 14 pilot gold
files and all 112 public English ArgMicrotexts files. Of the 112 files, 39
required 44 inserted span groups. The smoke-test gold and generated prediction
were already binary and required no inserted groups. Unit tests cover
left/right attachment order, multinuclear nuclei, idempotence, schema
validation, output collision protection, and batch-atomic validation.
