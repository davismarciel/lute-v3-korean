# Lexical integrity audit

Date: 2026-09-30. Read-only diagnosis of all 354 original lexical identities and all 352 rebuilt identities.

## Method

All lexical occurrence links were scanned in one joined query for canonical membership, source/surface offsets, raw subspan bounds, known contaminations, and multiple eligible heads. Copula/bound-noun exclusions do not manufacture multi-item findings. No records were repaired in place.

## Findings

| Severity | Before link findings | After link findings |
| --- | ---: | ---: |
| critical | 2 | 0 |
| important | 6 | 0 |
| minor | 0 | 0 |
| expected Kiwi behavior | 70 | 68 |

Counts are linked occurrences, not unique bugs. Two critical lexical misprojections were reproduced and corrected generically. Zero canonical-membership, source-offset or raw-subspan violations were found after rebuilding.

## Reviewed remaining cases

| Classification | Case | Decision |
| --- | --- | --- |
| important representation limitation | 물어봐도 → 묻다 + 보다 | Real auxiliary sequence; no -어 보다 pattern is tracked. Retain raw lexical identities; do not invent a lexical merge or suppression. Future construction support must be explicitly defined. |
| expected Kiwi behavior | 게임하고 / 설거지할 → noun + 하다 | Variable noun-plus-predicate projection. Retain compositional analysis; not evidence that every such noun is a single lexicalized verb. |
| expected Kiwi behavior | 그다음에 / 아무것도 / 아무데도 | Multiple compositional heads; no blanket semantic concatenation. |
| minor granularity limitation | 치즈버거를 / 오페라하우스… | Korean-written loanword components; retain provenance for later reviewed identity decisions. |
| expected Kiwi behavior | 십구 / 구십 / 열하나… | Compositional numeral heads; not span contamination. |
| expected Kiwi behavior | pronoun/verb contractions 제/전/갔/몰… | Surface spelling need not contain a full lemma; substring matching cannot certify lexical integrity. |

The important cross-unit NNP finding was reproduced for three real Sources and fixed by full-token occurrence projection (two regression fixtures); six partial linked occurrences became three complete name occurrences. No additional canonical rule was installed for the remaining ambiguous or compositional cases. They are not automatically repaired, removed, or declared acquired. The audit is a deterministic symptom detector, not a comprehensive semantic correctness proof.

## Attested corrections

| Original note ID | Surface | Raw heads | Canonical heads | Rule |
| --- | --- | --- | --- | --- |
| 1784072371737 | 어제 | 어 + 저 | 어제 | ko.lexical.eoje.v1 |
| 1787372615182 | 재미있는데 | 재미 + 있다 | 재미있다 | ko.lexical.existential-compound.v1 |

## All original 어제 occurrences

| Original note ID | Surface | Original projected heads | Rebuilt projected heads |
| --- | --- | --- | --- |
| 1784072371737 | 어제 | 어 + 저 | 어제 |
| 1786288612384 | 어제 | 어제 | 어제 |
| 1786288612390 | 어제 | 어제 | 어제 |
| 1786594444249 | 어제 | 어제 | 어제 |
| 1788368907769 | 어제 | 어제 | 어제 |
| 1789351915693 | 어제는 | 어제 | 어제 |
| 1789443048523 | 어제 | 어제 | 어제 |
| 1790397672974 | 어제 | 어제 | 어제 |
| 1790397812672 | 어제 | 어제 | 어제 |
