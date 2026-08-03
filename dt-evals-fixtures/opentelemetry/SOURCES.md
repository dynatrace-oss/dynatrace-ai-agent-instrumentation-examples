# Dataset sources & attribution

Fixture content comes from two sources (see `../SPEC.md` §3.7):

- **9 evaluators** are built from established evaluation datasets whose license
  permits public redistribution of small excerpts (MIT / Apache-2.0 / CC-BY-4.0).
- **5 evaluators** (faithfulness, answer-completeness, context-relevance, bias,
  user-frustration) use short, **self-authored** content, because their natural
  source datasets were not permissively licensed for redistribution in a public
  repo (gated / non-commercial / share-alike / unlicensed). Those cases are
  original to this repo, carry no third-party license, and are marked
  `source.origin: "authored"` in `fixtures.json`.

This file records, per evaluator, which dataset (or authored content) feeds it
and how the pass/fail ground truth is derived. Per-dataset licenses and credits
are in [Licenses & attribution](#licenses--attribution) below.

`build_fixtures.py` reads these from the local HuggingFace cache. The `source`
field on each case records the exact dataset, row, and (where used) the
`scaffold` half.

> **Scaffolded cases.** A few evaluators score only one side of a turn and their
> source dataset provides only that side. There, the **evaluated** half is real
> dataset content and the **non-evaluated** half is a fixed generic scaffold
> string (`user` or `response`), recorded as `source.scaffold`. See the
> "scaffold" column below.

| Evaluator | Dataset | HF repo | Ground truth (pass / fail) | Scaffold |
|-----------|---------|---------|----------------------------|----------|
| toxicity | Anthropic HH-RLHF (harmless-base) | [`Anthropic/hh-rlhf`](https://huggingface.co/datasets/Anthropic/hh-rlhf) | `chosen` (harmless) / `rejected` (toxic) | — |
| fluency | SODA-Eval | [`Johndfm/soda_eval`](https://huggingface.co/datasets/Johndfm/soda_eval) | score-5, no issues / issue-flagged | — |
| faithfulness | Synthetic (authored) | — | answer grounded in context / not grounded | — |
| hallucination | FinQA hallucination detection | [`Cleanlab/FinQA-hallucination-detection`](https://huggingface.co/datasets/Cleanlab/FinQA-hallucination-detection) | `is_correct` grounded / hallucinated | — |
| relevance | HelpSteer2 | [`nvidia/HelpSteer2`](https://huggingface.co/datasets/nvidia/HelpSteer2) | high / low `helpfulness` | — |
| factual-accuracy | TruthfulQA | [`domenicrosati/TruthfulQA`](https://huggingface.co/datasets/domenicrosati/TruthfulQA) | best answer / incorrect answer | — |
| answer-completeness | Synthetic (authored) | — | complete answer / omits requested part | — |
| pii-leakage | NVIDIA Nemotron-PII | [`nvidia/Nemotron-PII`](https://huggingface.co/datasets/nvidia/Nemotron-PII) | generic description / PII text | user |
| summarization-quality | SummEval | [`mteb/summeval`](https://huggingface.co/datasets/mteb/summeval) | most / least consistent summary | user |
| prompt-injection | Neuralchemy prompt-injection | [`neuralchemy/Prompt-injection-dataset`](https://huggingface.co/datasets/neuralchemy/Prompt-injection-dataset) | benign / injection input | response |
| context-relevance | Synthetic (authored) | — | relevant / irrelevant retrieved doc | response |
| conciseness | daloopa financial-retrieval | [`daloopa/financial-retrieval`](https://huggingface.co/datasets/daloopa/financial-retrieval) | high / low `conc_rating` | — |
| user-frustration | Synthetic (authored) | — | calm / frustrated user turn | response |
| bias | Synthetic (authored) | — | unbiased / stereotype statement | user |

## Consuming these fixtures in dt-evals (span-field contract)

The spans carry the standard `gen_ai.input.messages` / `gen_ai.output.messages`,
which dt-evals reads by default. Grounding context and reference are emitted on
**custom attributes** (there is no OTel GenAI standard for them, and dt-evals
ships no default context field). To score the grounding evaluators, the dt-evals
config must map them:

```yaml
scope:
  spanFields:
    context: gen_ai.context      # faithfulness, hallucination, context-relevance, summarization-quality
    # reference: gen_ai.reference  # only if a reference-based evaluator needs it
```

Without `spanFields.context: gen_ai.context`, dt-evals runs those evaluators
with no source, so their pass/fail cases will not score as intended. (Note: the
instrumentation emits the system prompt as `gen_ai.system_instructions` — plural
— while dt-evals' default is `gen_ai.system_instruction`; map it if a metric
needs the system prompt.)

## Notes

- **Synthetic model & usage.** `gen_ai.request.model` (`gpt-4o-mini`) and
  `gen_ai.usage.*` are not from the source datasets (which carry no token
  counts): the model is a fixed default and usage is estimated deterministically
  from the content (~4 chars/token). They make the spans look production-shaped;
  evaluators do not read them.
- **Genuine multi-turn** comes only from datasets that carry conversations —
  HH-RLHF (toxicity) and SODA-Eval (fluency). All other cases are single-turn
  rows (real or authored) embedded as one-turn conversations.
- **Content warning.** By design, some fixtures contain deliberately toxic,
  biased, or PII-shaped text — they are test inputs for the toxicity, bias, and
  pii-leakage evaluators. The PII is synthetic (from NVIDIA Nemotron-PII or
  self-authored); none of it is real personal data.

## Licenses & attribution

Only datasets whose license permits public redistribution of small excerpts are
committed here; the rest were replaced with self-authored content (see the intro).
Each committed excerpt is small (a handful of rows).

| Dataset | License | Credit |
|---------|---------|--------|
| [Anthropic/hh-rlhf](https://huggingface.co/datasets/Anthropic/hh-rlhf) | MIT | Anthropic |
| [Johndfm/soda_eval](https://huggingface.co/datasets/Johndfm/soda_eval) | CC-BY-4.0 | Mendonça, Trancoso & Lavie (SODA-Eval); SODA by Kim et al. |
| [Cleanlab/FinQA-hallucination-detection](https://huggingface.co/datasets/Cleanlab/FinQA-hallucination-detection) | MIT | Cleanlab; FinQA by Chen et al. |
| [nvidia/HelpSteer2](https://huggingface.co/datasets/nvidia/HelpSteer2) | CC-BY-4.0 | NVIDIA |
| [domenicrosati/TruthfulQA](https://huggingface.co/datasets/domenicrosati/TruthfulQA) | Apache-2.0 | Lin, Hilton & Evans (TruthfulQA) |
| [nvidia/Nemotron-PII](https://huggingface.co/datasets/nvidia/Nemotron-PII) | CC-BY-4.0 | NVIDIA |
| [mteb/summeval](https://huggingface.co/datasets/mteb/summeval) | MIT | SummEval by Fabbri et al. |
| [neuralchemy/Prompt-injection-dataset](https://huggingface.co/datasets/neuralchemy/Prompt-injection-dataset) | Apache-2.0 | neuralchemy |
| [daloopa/financial-retrieval](https://huggingface.co/datasets/daloopa/financial-retrieval) | MIT | Daloopa |
| Synthetic (faithfulness, answer-completeness, context-relevance, bias, user-frustration) | Apache-2.0 (this repo) | authored for this repo |

Attribution is provided under each dataset's license terms. The stated license
covers the dataset packaging; a couple of these re-package third-party source
text (SummEval → CNN/DailyMail; FinQA → SEC filings), of which only small
excerpts appear here. If you spot a licensing concern, please open an issue.
