# NemoClaw Assessment — Why We're Not Using It (Yet)

## Status: Rejected (Decision D6) · March 2026

---

## Summary

NemoClaw was announced at GTC 2026 (March 16) as NVIDIA's enterprise-grade wrapper around
OpenClaw — adding Nemotron models, the OpenShell runtime, policy-based security, and
sandboxed execution. On paper, it's the perfect brain for a Jarvis-style assistant running
on DGX Spark. In practice, it's not production-ready.

This document captures the evidence so the decision can be revisited when NemoClaw matures.

---

## What NemoClaw Promises

- Single-command installation of OpenClaw + Nemotron models + OpenShell runtime
- Sandboxed execution with kernel-level isolation (Landlock, seccomp, network namespaces)
- Privacy router for local-first inference with cloud fallback
- Policy-based security — declarative YAML controlling network, filesystem, process, inference
- Nemotron 3 Super (120B MoE, 12B active) running locally on DGX Spark
- Always-on, self-evolving agents

---

## What the Community Is Actually Experiencing (March 2026)

### OpenShell Gateway Failures
- GitHub Issue #341: `nemoclaw onboard` fails at "Starting services" with gRPC/etcd
  connection closure and `/readyz` health check timeout on fresh DGX Spark instances
- GitHub Issue #415: k3s rejects `-resolv-conf` flag — the entrypoint script has a
  single-dash vs double-dash bug that prevents the gateway container from starting
- GitHub Issue #878: Embedded k3s fails on DGX Spark GB10 (ARM64, Ubuntu 24.04, cgroup v2)
  — all system pods stuck in CrashLoopBackOff, blocking onboarding entirely

### Provider Configuration Broken
- NVIDIA Developer Forums: Step 7 of the playbook gives `provider 'ollama-local' not found`
  errors — users must manually create provider entries that should exist after onboarding
- The playbook documentation doesn't match the actual software state

### NIM Local Inference Failing Silently
- NVIDIA Developer Forums: NIM installation appears to complete but silently fails over to
  NVIDIA Cloud — defeating the entire purpose of running locally on the Spark
- Users who want local inference (the primary value proposition) can't get it working

### Community Assessment
- Respected community member (eugr, maintainer of the community vLLM Docker image that
  actually works): described the situation as reminiscent of the "Spark Cookbook situation"
  where NVIDIA published guides that didn't work
- Another community member (cosinus) warned that "even if some marketing people tried to
  tell 'it's super easy to do supercomputing' with a Spark... it's a developer box. Still
  bleeding edge at some spots"
- One user described 15 days of trying as "total chaos total complete ultra utter chaos"

### NemoClaw Is Alpha Software
- Installation guides explicitly acknowledge alpha status with "rough edges"
- Docker conflicts, cgroup issues, and OOM kills are documented as known problems
- macOS has partial support but local inference doesn't work properly
- The sandbox image is ~2.4 GB and multiple heavy processes run simultaneously

---

## Pattern Recognition

This follows the exact pattern seen repeatedly with NVIDIA DGX Spark software:

1. **NVFP4 saga** — NVIDIA marketed native FP4 support, but the community (Avarok, eugr)
   spent months getting it working through workarounds
2. **Nemotron 3 Super launch** — Model announced for Spark but vLLM path needed
   community patches
3. **NemoClaw** — Announced with polish at GTC, but actual DGX Spark support has
   fundamental infrastructure issues (k3s, cgroup v2, provider config)

**Marketing consistently runs 3-6 months ahead of engineering for Spark-specific support.**

---

## Why Our DeepAgents SDK Path Is Better Right Now

| Dimension | NemoClaw | DeepAgents SDK |
|-----------|----------|---------------|
| **Stability** | Alpha, fundamental infrastructure bugs | Proven across 3 templates, 11+ factory runs |
| **GB10 support** | Gateway won't start, NIM fails silently | vLLM + Qwen3-Coder-Next stable and battle-tested |
| **Time to value** | Unknown — debugging sandbox policies before any useful work | Immediate — templates ready, exemplar proven |
| **Infrastructure** | Embedded k3s, Docker-in-Docker, OpenShell gateway | Direct vLLM, NATS, existing Docker setup |
| **Risk** | Every weekend could be lost to config debugging | Known patterns, known failure modes |
| **Provider independence** | Locked to NVIDIA ecosystem (Nemotron, NIM, OpenShell) | Any model via vLLM, any cloud API via config |

---

## When to Revisit

Monitor these signals:

1. **GitHub Issues #341, #415, #878 resolved** — The gateway actually starts on DGX Spark
2. **NIM local inference working** — Users confirm local-only mode without cloud fallback
3. **NVIDIA driver 590 shipped via apt** — The NVFP4 unlock (separate issue but related maturity signal)
4. **Community Docker image for NemoClaw** — When eugr or similar builds a "it just works" alternative
5. **DGX Spark clustering software update** — NVIDIA announced up to 4-node clustering; when that ships and works, the whole Spark ecosystem will have matured

**Estimated timeline:** 3-6 months (Q3-Q4 2026) before NemoClaw is viable on DGX Spark.

**Future role if it matures:** NemoClaw could become an alternative runtime for always-on
agents, particularly the General Purpose Agent. The OpenShell sandbox security model is
genuinely interesting for an agent with broad tool access. But it would complement our
NATS + DeepAgents architecture, not replace it.

---

## References

- NVIDIA NemoClaw announcement: https://nvidianews.nvidia.com/news/nvidia-announces-nemoclaw
- GitHub Issues: #341 (gateway timeout), #415 (resolv-conf flag), #878 (k3s cgroup v2)
- NVIDIA Developer Forums: "Errors with NemoClaw DGX Spark playbook", "NemoClaw won't install NIMs on DGX Spark"
- GTC 2026 blog: https://blogs.nvidia.com/blog/rtx-ai-garage-gtc-2026-nemoclaw/
