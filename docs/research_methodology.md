# Varynx — Research Methodology

**Document:** T11.1 Research Methodology  
**Project:** Cloud-Native Behavioral Risk Control for Autonomous AI Agents  
**Status:** Phase 1 MVP — Research design completed prior to any experimental execution  
**Research Integrity:** All hypotheses are defined prospectively. No results are pre-claimed.

---

## 1. Central Research Question

> Can a cloud-native behavioral risk control engine operating on structured event streams from autonomous AI agents — without access to model internals — produce security-relevant signals (anomaly detection, trust scoring, and pre-action risk projection) that are measurably more informative than static rule-based baselines, while maintaining auditability and reproducibility?

---

## 2. Falsifiable Hypotheses

All four hypotheses are defined prior to experimental execution. No outcome is assumed.

| ID | Hypothesis | Independent Variable | Dependent Variable | Evaluation |
|----|-----------|---------------------|-------------------|------------|
| H1 | Multi-dimensional behavioral evidence will detect anomalous agent behavior with higher F1 than a single-dimension rule-based baseline on the same synthetic scenario datasets. | Detection system (Varynx vs B2) | F1 score on labeled scenarios | T9.2, T12.1 |
| H2 | A Behavioral_Trust_Score updated after each event will reflect behavioral changes within a measurably shorter number of events than a session-averaged score. | Update frequency (per-event vs session-end) | Events-to-detection count | T9.2, T12.1 |
| H3 | BCSE projected risk levels will agree with ground-truth anomaly classification at a rate greater than chance and greater than a naive always-LOW prior. | BCSE projection | Agreement with ground truth | T9.2, T12.1 |
| H4 | The Adaptive_Response_Engine will escalate recommendations in proportion to Behavioral_Trust_Score decline rate. | Score decline rate | Events-to-escalation | T9.2, T12.1 |

---

## 3. Study Design

### 3.1 Type

Simulation-based experimental study using controlled synthetic scenario datasets.

### 3.2 Units of Analysis

- Agent sessions (primary)
- Individual Behavioral_Events (secondary)
- Per-scenario evaluation runs (tertiary)

### 3.3 Scenario Dataset

Scenario files are YAML-formatted, versioned, and stored under `scenarios/`. Each scenario defines:
- Agent identity and declared scopes
- Ordered sequence of behavioral events with ground-truth anomaly annotations
- Expected response recommendations (for H4)

Scenarios are authored prior to evaluation. Ground-truth annotations are never modified after authoring to match observed results (REQ-025.6).

### 3.4 Baselines

| Baseline | Description | Purpose |
|----------|-------------|---------|
| B1 (always-PERMIT) | Never flags any event | Null hypothesis reference for H1 |
| B2 (single-dimension) | Only counts authorization denials | H1 comparison: single vs. multi-dimension |
| B3 (session-average) | Computes trust only at session end | H2 comparison: per-event vs. session-average |

### 3.5 Ablation Design

The six evidence detectors can be disabled individually via `config/evaluation_config.yaml`. Ablation runs isolate the contribution of each detector to overall detection performance.

---

## 4. Controlled Variables

| Variable | Control Method |
|----------|---------------|
| Random seed | Fixed via `evaluation_config.yaml` (default: 42) |
| Configuration snapshot | Captured in every evaluation report |
| Software version | Pinned in `pyproject.toml` |
| Scenario files | Versioned YAML; never modified post-authoring |
| Policy file | `config/default_policy.yaml` version string |

---

## 5. Measurement Plan

All metrics are computed from pipeline outputs on real scenario inputs. No interpolation or fabrication is permitted.

| Metric | Computation | Task |
|--------|-------------|------|
| Precision | TP / (TP + FP) across labeled events | T9.3 |
| Recall | TP / (TP + FN) across labeled events | T9.3 |
| F1 | 2 × P × R / (P + R) | T9.3 |
| Events-to-detection | Event index of first correct anomaly signal | T9.3 |
| Mean, std, 95% CI | Across ≥5 evaluation runs | T9.4 |
| Effect size (Cohen's d) | Between Varynx and each baseline | T9.4 |

---

## 6. Reproducibility Requirements

- `reproduce.sh` (T12.3) installs dependencies, runs all scenarios, and writes evaluation reports to `output/`.
- Fixed random seed is required for all evaluation runs.
- All scenario YAML files and configuration snapshots are included in the repository.
- Results must be independently reproducible from the published scenario files.

---

## 7. Limitations and Assumptions

- Varynx is evaluated on synthetic scenarios, not production agent traffic. Real-world generalizability requires additional validation.
- Thresholds and scoring weights are initial proposals requiring empirical calibration. No pre-trained thresholds are claimed as optimal.
- The BCSE component is a Phase 1 stub. H3 cannot be meaningfully evaluated until the Phase 2 engine is implemented.
- The Predictive Intelligence component is a Phase 1 stub. Trajectory-based hypotheses require Phase 2 implementation.
- No performance SLA (NFR-PERF-001 through NFR-PERF-003) can be claimed until T12.4 benchmarks are executed.