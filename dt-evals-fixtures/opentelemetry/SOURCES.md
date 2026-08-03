# Dataset sources & attribution

Every fixture in `fixtures.json` is built from a real, established evaluation
dataset — never hand-authored (see `../SPEC.md` §3.7). This file records, per
dataset, which evaluator it feeds, how the pass/fail ground truth is derived,
and its upstream source for attribution.

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
| faithfulness | FaithEval (counterfactual) | [`Salesforce/FaithEval-counterfactual-v1.0`](https://huggingface.co/datasets/Salesforce/FaithEval-counterfactual-v1.0) | answer grounded in context / not | — |
| hallucination | FinQA hallucination detection | [`Cleanlab/FinQA-hallucination-detection`](https://huggingface.co/datasets/Cleanlab/FinQA-hallucination-detection) | `is_correct` grounded / hallucinated | — |
| relevance | HelpSteer2 | [`nvidia/HelpSteer2`](https://huggingface.co/datasets/nvidia/HelpSteer2) | high / low `helpfulness` | — |
| factual-accuracy | TruthfulQA | [`domenicrosati/TruthfulQA`](https://huggingface.co/datasets/domenicrosati/TruthfulQA) | best answer / incorrect answer | — |
| answer-completeness | Magneto QA (LLM judge) | [`Magneto/qa-dataset-llm-judge-flattened`](https://huggingface.co/datasets/Magneto/qa-dataset-llm-judge-flattened) | `COMPLETE` / `INCOMPLETE` | — |
| pii-leakage | NVIDIA Nemotron-PII | [`nvidia/Nemotron-PII`](https://huggingface.co/datasets/nvidia/Nemotron-PII) | generic description / PII text | user |
| summarization-quality | SummEval | [`mteb/summeval`](https://huggingface.co/datasets/mteb/summeval) | most / least consistent summary | user |
| prompt-injection | Neuralchemy prompt-injection | [`neuralchemy/Prompt-injection-dataset`](https://huggingface.co/datasets/neuralchemy/Prompt-injection-dataset) | benign / injection input | response |
| context-relevance | GooAQ context-relevance | [`zilliz/gooaq-context-relevance-130k-context-relevance-with-think`](https://huggingface.co/datasets/zilliz/gooaq-context-relevance-130k-context-relevance-with-think) | relevant / irrelevant retrieved doc | response |
| conciseness | daloopa financial-retrieval | [`daloopa/financial-retrieval`](https://huggingface.co/datasets/daloopa/financial-retrieval) | high / low `conc_rating` | — |
| user-frustration | IEMOCAP | [`AbstractTTS/IEMOCAP`](https://huggingface.co/datasets/AbstractTTS/IEMOCAP) | calm / frustrated user turn | response |
| bias | StereoSet | [`McGill-NLP/stereoset`](https://huggingface.co/datasets/McGill-NLP/stereoset) | anti-stereotype / stereotype sentence | user |

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

- **Genuine multi-turn** comes only from datasets that carry conversations —
  HH-RLHF (toxicity) and SODA-Eval (fluency). All other cases are real
  single-turn rows embedded as one-turn conversations.
- **bias** originally targeted Social Bias Frames (SBIC); its HuggingFace loader
  is a deprecated dataset script, so StereoSet — another standard bias benchmark
  — is used instead.
- **Licensing — verify before external redistribution.** These excerpts are
  used here for regression-testing an eval pipeline. Each upstream dataset has
  its own license/terms (e.g. HH-RLHF is MIT; HelpSteer2 is CC-BY-4.0; StereoSet
  is CC-BY-SA-4.0; IEMOCAP requires an academic-use agreement). Confirm each
  dataset's terms permit committing small excerpts before publishing this repo
  externally. (Tracked as an open item in `../SPEC.md` §9.)
