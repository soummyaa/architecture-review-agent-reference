# Captured reference runs

The three gated decision runs, rendered clean-approval ADR, and setup validation
outputs were generated on 2026-09-05 from the synthetic workshop submissions.
The non-gated SUB-005 discussion run was added on 2026-09-06.

- `SUB-003-clean-approval.json`: clean approval
- `SUB-002-clear-rejection.json`: clear rejection
- `SUB-001-conditional-approval.json`: approval with conditions
- `SUB-003-clean-approval.docx`: rendered clean-approval ADR
- `validator-output.txt`: validator output; the live request ID was redacted
- `preflight-output.txt`: workstation preflight output
- `SUB-005-lenient-cross-cloud-token-exchange.json`: non-gated, lenient result
	retained for workshop discussion, not a reference-quality expected outcome

Live SUB-001, SUB-002, and SUB-003 runs should preserve the gated decision
behavior demonstrated here, but their wording can differ because model output
is not fully deterministic. SUB-005 is discussion-only and has no fixed
expected decision.