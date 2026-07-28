# Trinity at Sapien Demo Day — 5-Minute Script

- **Event:** Sapien Builder Circle Demo Day
- **Time:** July 31, 2026, 3:00 PM ET / August 1, 2026, 4:00 AM KST
- **Format:** Pre-recorded screen share with English captions
- **Target length:** 5 minutes
- **Audience:** Sapien team, engineers, and Builder Circle members

## Recording Plan

Use a prepared Trinity workflow rather than waiting for live provider execution.
Keep the cursor still while speaking, switch screens only at the marked cues, and
show English captions throughout.

| Time | Screen |
| --- | --- |
| 0:00–0:35 | Trinity title and GitHub repository |
| 0:35–1:20 | Single-agent versus Trinity role separation |
| 1:20–2:50 | Start → Nexus → Blueprint → Execution Matrix → Review |
| 2:50–4:15 | Trinity → Sapien PoQ → Approve or Replan |
| 4:15–5:00 | GitHub, PyPI, and PoQ pilot question |

---

## 0:00–0:35 — Introduction

**Screen:** Trinity logo and GitHub repository

### English

> Hi everyone, I’m Seungho from Korea. Thank you to Tyler and the Sapien team
> for inviting me.
>
> Because of the time difference, I prepared this short recorded demo.
>
> This is Trinity — “Three minds, one context.”
>
> Trinity is an open-source multi-agent AI orchestrator that coordinates Claude
> Code, Codex, and Antigravity before they make changes to a real software
> project.

### 한국어 해석

안녕하세요. 저는 한국에서 온 승호입니다. 저를 초대해 주신 Tyler와 Sapien 팀에
감사드립니다.

시차 때문에 짧은 녹화 데모를 준비했습니다.

이 프로젝트는 Trinity입니다. 슬로건은 “세 개의 지능, 하나의 컨텍스트”입니다.

Trinity는 Claude Code, Codex, Antigravity가 실제 소프트웨어 프로젝트를 변경하기
전에 서로 협업하도록 조율하는 오픈소스 멀티 에이전트 AI 오케스트레이터입니다.

---

## 0:35–1:20 — The Problem

**Screen:** A single AI compared with Trinity’s three-agent structure

### English

> Most AI coding tools ask one model to plan the work, implement it, and then
> judge its own result.
>
> That is fast, but it creates a trust problem. The same model can make a wrong
> assumption, implement it confidently, and then approve its own mistake.
>
> Trinity separates those responsibilities.
>
> Claude acts mainly as the architect, Codex as the implementer, and
> Antigravity as the reviewer. They share the same project context, but they
> approach the problem from different roles.

### 한국어 해석

대부분의 AI 코딩 도구는 하나의 모델에 계획, 구현, 결과 검토를 모두 맡깁니다.

이 방식은 빠르지만 신뢰성 문제가 발생합니다. 동일한 모델이 잘못된 가정을 하고,
그것을 자신 있게 구현한 뒤, 자신의 실수까지 승인할 수 있기 때문입니다.

Trinity는 이러한 책임을 분리합니다.

Claude는 주로 설계자, Codex는 구현자, Antigravity는 검토자 역할을 맡습니다.
세 에이전트는 동일한 프로젝트 컨텍스트를 공유하지만 서로 다른 관점에서 문제를
다룹니다.

---

## 1:20–2:50 — Trinity Workflow Demo

**Screen:** Start → Nexus → Blueprint → Execution Matrix → Review

### English

> Let me show a prepared workflow.
>
> I give Trinity a goal: analyze an existing codebase, identify the most
> important problem, and implement a safe fix.
>
> First, Trinity detects the available AI providers and stores the goal,
> selected agents, and project context in a persistent workflow.
>
> The agents then deliberate in rounds. Each agent returns its proposed
> approach, risks, and implementation direction.
>
> A central agent synthesizes those opinions. If important information is
> missing, Trinity pauses and asks the user a question instead of silently
> making an assumption.
>
> Once the plan is clear, Trinity creates an executable blueprint and divides
> it into work packages.
>
> Nothing is written to the project yet. The user must approve execution and
> select the target workspace.
>
> After approval, each package is assigned according to the agents’ roles and
> strengths. Dependencies and file ownership are checked before packages run
> in parallel.
>
> When a package is completed, the agent that did not implement it reviews the
> result.
>
> If the review finds a required problem, Trinity does not simply mark the
> workflow as complete. It creates a supplemental work package, returns to the
> blueprint stage, and waits for the user to approve the correction.

### 한국어 해석

미리 준비한 워크플로를 보여드리겠습니다.

저는 Trinity에 기존 코드베이스를 분석하고, 가장 중요한 문제를 찾아 안전하게
수정하라는 목표를 전달합니다.

먼저 Trinity는 사용할 수 있는 AI 공급자를 감지하고 목표, 선택된 에이전트,
프로젝트 컨텍스트를 지속 가능한 워크플로에 저장합니다.

그다음 에이전트들이 여러 라운드에 걸쳐 토론합니다. 각 에이전트는 자신의 접근
방법, 위험 요소, 구현 방향을 제안합니다.

중앙 에이전트가 이 의견들을 종합합니다. 중요한 정보가 부족하면 Trinity는
임의로 가정하지 않고 작업을 멈춘 뒤 사용자에게 질문합니다.

계획이 명확해지면 Trinity는 실행 가능한 블루프린트를 만들고 이를 여러 작업
패키지로 나눕니다.

이 단계까지는 프로젝트 파일을 변경하지 않습니다. 사용자가 실행을 승인하고 대상
작업공간을 선택해야 합니다.

승인 후에는 각 에이전트의 역할과 강점에 따라 작업 패키지가 배정됩니다. 병렬 실행
전에는 의존성과 파일 소유권도 확인합니다.

하나의 작업 패키지가 완료되면 그것을 구현하지 않은 다른 에이전트가 결과를
검토합니다.

검토 과정에서 반드시 수정해야 할 문제가 발견되면 Trinity는 워크플로를 완료
처리하지 않습니다. 추가 작업 패키지를 만들고 블루프린트 단계로 돌아가 사용자의
수정 실행 승인을 기다립니다.

---

## 2:50–4:15 — Connecting Trinity with Sapien PoQ

**Screen:** Trinity → Sapien PoQ → Approve or Replan

### English

> This is where I believe Trinity connects naturally with Sapien’s Proof of
> Quality.
>
> Trinity reduces single-model risk through deliberation and peer review. But
> agreement between multiple AI models is still not independent proof that the
> result is correct.
>
> The integration I want to explore is an external PoQ gate at the blueprint or
> final-review stage.
>
> Trinity could send Sapien a structured review package containing the original
> goal, the proposed result, each agent’s reasoning, important disagreements,
> supporting evidence, and the internal review outcome.
>
> Sapien validators could then return their individual verdicts, confidence
> scores, additional evidence, and overall consensus strength.
>
> Trinity could use that response as a workflow decision. A strong validation
> result could approve the next stage. A disputed or low-confidence result
> could return the workflow to replanning and create new corrective work
> packages.
>
> This would combine machine-scale deliberation with independent human
> judgment, while keeping a traceable record of how the final decision was
> reached.

### 한국어 해석

바로 이 지점에서 Trinity가 Sapien의 Proof of Quality와 자연스럽게 연결될 수
있다고 생각합니다.

Trinity는 토론과 동료 검토를 통해 단일 모델의 위험을 줄입니다. 하지만 여러 AI
모델이 서로 동의했다고 해서 그 결과가 정확하다는 독립적인 증거가 되는 것은
아닙니다.

제가 탐색하고 싶은 통합 방식은 블루프린트 또는 최종 검토 단계에 외부 PoQ 검증
관문을 추가하는 것입니다.

Trinity는 원래 목표, 제안된 결과, 각 에이전트의 추론, 중요한 이견, 근거 자료,
내부 검토 결과가 포함된 구조화된 검토 패키지를 Sapien에 보낼 수 있습니다.

Sapien 검증자들은 개별 판정, 신뢰도 점수, 추가 근거, 전체 합의 강도를 반환할 수
있습니다.

Trinity는 이 결과를 워크플로 결정에 사용할 수 있습니다. 검증 결과가 강하면 다음
단계를 승인하고, 의견이 갈리거나 신뢰도가 낮으면 다시 계획 단계로 돌아가 수정
작업 패키지를 생성할 수 있습니다.

이 구조는 기계가 제공하는 확장 가능한 토론 능력과 독립적인 인간의 판단을
결합하면서, 최종 결정이 만들어진 과정을 추적 가능한 기록으로 남깁니다.

---

## 4:15–5:00 — Closing and Pilot Question

**Screen:** GitHub, PyPI, and “PoQ Pilot?”

### English

> AI agents are moving from answering questions to taking actions.
>
> When an agent can modify code, deploy software, or influence important
> decisions, quality cannot depend only on the confidence of one model — or
> even agreement between several models.
>
> Trinity provides the structured workflow, agent disagreement, review
> artifacts, and correction loop. Sapien could provide the independent quality
> layer.
>
> Trinity is open source and available today through GitHub and PyPI.
>
> My main question for the Sapien team is: what should be the first unit of PoQ
> validation — a blueprint, a completed work package, or the final review?
>
> I would love to explore a small pilot with the Sapien team.
>
> Thank you for watching.

### 한국어 해석

AI 에이전트는 이제 질문에 답하는 단계를 넘어 실제 행동을 수행하는 단계로
이동하고 있습니다.

에이전트가 코드를 변경하고, 소프트웨어를 배포하거나, 중요한 결정에 영향을 줄 수
있다면 결과의 품질을 하나의 모델이 가진 자신감이나 여러 모델의 합의에만 의존할 수
없습니다.

Trinity는 구조화된 워크플로, 에이전트 간 이견, 검토 자료, 수정 반복 과정을
제공합니다. Sapien은 여기에 독립적인 품질 검증 계층을 제공할 수 있습니다.

Trinity는 오픈소스이며 현재 GitHub와 PyPI를 통해 사용할 수 있습니다.

Sapien 팀에 드리고 싶은 핵심 질문은 이것입니다. PoQ로 가장 먼저 검증해야 할
단위는 블루프린트일까요, 완료된 작업 패키지일까요, 아니면 최종 검토 결과일까요?

Sapien 팀과 작은 파일럿을 진행해 보고 싶습니다.

시청해 주셔서 감사합니다.

---

## Recording Checklist

- [ ] Use a prepared successful workflow; do not wait for live provider calls.
- [ ] Record at 1080p with the terminal font large enough to read.
- [ ] Add English captions.
- [ ] Keep each screen aligned with the timing table.
- [ ] Describe the PoQ connection as a proposed pilot, not a shipped feature.
- [ ] End on the repository URL and `pipx install trinity-agent`.
- [ ] Keep the final recording at or below five minutes.

## Final Screen

```text
Trinity — Three minds, one context.

GitHub: https://github.com/hongdangmoo49/Trinity
PyPI:   https://pypi.org/project/trinity-agent/

pipx install trinity-agent
```
