# Advisory decision models

Status: implementation complete. Real-data qualification remains optional and requires separate owner authorization.

## Current setup and limits

`decide` provides the Workers AI client and bounded JSONL evaluator. `orchestrate` provides opt-in shadow or advisory tier consultation. See [agent setup](docs/agent-setup.md#configure-optional-workers-ai-decisions) for operation and configuration.

The account-scoped `usr-decision-models` token has Workers AI Read and Write permissions and expires on 2027-10-22. The token and account ID are stored in the local `vault`. Do not print, replace, or copy their values into repository files. If either entry is absent or expires, park credential-dependent work for the owner. Local tests remain executable.

The owner selected Workers AI Free only. Do not upgrade Workers, enable AI Gateway credits, change R2, or deploy resources. Live calls require separate authorization. Keep advice subordinate to existing model, tier, permission, and verification rules.

One synthetic request verified the live REST envelope and the `choice`, `noul`, and `score` answers. Live task evaluation, Linux behavior, real-data quality, and measured economics remain unverified. No savings have been established.

## Optional qualification

For optional qualification, the owner may provide 30–50 representative real historical briefs, independently label and sanitize them, group them by source, and authorize at most 50 live calls per run. Keep rubric-development and held-out sources disjoint. Report classifier quality separately from value in real sessions.

Only after classification review, ask the owner to authorize a matched-session comparison on real coding tasks: current routing versus advisory routing. Compare task success, applicable verification, total wall latency, retries and recovery, and full primary-model usage including normal input, cache reads/writes, and output. Include added decision-call/context overhead. Subscription quotas are not list-price API costs. If usage or price inputs are incomplete, report cost as `unknown`; claim no savings until observed evidence supports it.
