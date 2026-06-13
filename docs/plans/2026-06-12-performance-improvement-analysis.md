# Trinity 성능개선 분석 보고서

작성일: 2026-06-12

브랜치: `feature/current-workflow-operation-analysis`

기준 소스: Trinity `0.12.9`

관련 문서:

- `docs/plans/2026-06-12-current-workflow-operation-analysis.md`
- `docs/plans/2026-06-12-harness-design-analysis.md`

## 목적

이 문서는 현재 Trinity workflow 구조를 기준으로 성능 병목 후보를 분석하고, 어떤 순서로
개선해야 하는지 제안한다. 실제 최적화 작업 전에 필요한 기준 계측값, 위험 지점, 하네스
검증 항목도 함께 정리한다.

## 결론 요약

현재 active workflow 파일만 놓고 보면 즉시 치명적인 병목은 아니다. 다만 로컬 계측 기준으로
session이 이미 약 1.6MB이고 snapshot load도 수십 ms 단위까지 올라와 있다.

하지만 구조적으로 다음 조건이 겹치면 렉이 커질 가능성이 높다.

- workflow event가 수천 개 이상으로 증가
- archive session이 수백 개로 증가
- `shared.md` 또는 oversized backup이 계속 누적
- `/model` live discovery가 provider별로 긴 timeout을 소비
- Nexus/Execution/Report 화면이 snapshot을 반복 로드
- execution 중 WP 결과의 partial persist/UI/report 반영 계약이 약해 사용자가 반복적으로 화면을 전환/조회

따라서 우선순위는 "무작정 빠르게 만들기"가 아니라, 먼저 하네스 계측을 추가하고 현재
경로에서 재현되는 비용부터 낮추는 것이 맞다.

1. 성능 하네스와 current-state 재계측
2. workflow event load cache/tail/index
3. snapshot memoization and route projection cache
4. model discovery cache-first UI, provider별 병렬화, provider별 timeout
5. execution partial result의 UI/report 통합 계약 고정
6. report/inspector lazy loading
7. `.trinity` 대형 artifact retention/cleanup 명령

## 현재 상태 계측

계측 환경:

- 위치: `/home/zaemi/workspace/Trinity`
- 명령: `PYTHONPATH=src python3`
- active config: `.trinity/trinity.config`
- 반복: session/events 20회, snapshot 10회

주의:

- 이전 초안의 `/home/user/workspace/Trinity` 기준 수치에는 `.trinity` 3.5GB와
  `shared.md.oversized-*` 3.46GB가 포함되어 있었다.
- 현재 WSL 체크아웃 `/home/zaemi/workspace/Trinity`에는 100MB 초과 파일이 없고, `.trinity`
  전체 크기도 280MB다.
- 따라서 oversized cleanup은 현재 즉시 병목의 증거가 아니라 재발 방지용 운영 기능으로
  분류한다.

현재 `.trinity` 크기:

| 항목 | 크기 |
| --- | ---: |
| `.trinity` 전체 | 280MB |
| 100MB 초과 파일 | 없음 |
| `.trinity/workflow/session.json` | 1,589,743 bytes |
| `.trinity/workflow/events.jsonl` | 399,717 bytes |
| `.trinity/shared.md` | 182,984 bytes |
| `.trinity/memory/index.sqlite` | 163,840 bytes |

현재 active operation 계측:

| Operation | min | avg | max | 비고 |
| --- | ---: | ---: | ---: | --- |
| `load_session` | 12.10ms | 14.73ms | 19.01ms | active session 약 1.6MB |
| `load_events_all` | 2.21ms | 2.86ms | 4.91ms | events 447개 |
| `load_events_for_workflow` | 2.18ms | 2.50ms | 3.30ms | 전체 events read 후 filter |
| `snapshot_load` | 23.82ms | 28.33ms | 31.43ms | session/review 결과 증가 영향 |

해석:

- 현재 active session은 치명적으로 느리지는 않지만, snapshot load가 이미 수십 ms 단위로
  올라왔다.
- review result가 늘면서 `session.json` 자체가 커지고 있어 route 전환 때 반복 load가 쌓이면
  체감 지연이 생길 수 있다.
- event load는 아직 작지만 전체 read 후 filter 구조라 workflow가 커지면 선형 비용이 증가한다.
- oversized backup은 현재 경로에서 재현되지 않으므로 P1 병목이 아니라 cleanup/retention
  정책으로 분리한다.

## 병목 후보 상세

### 1. Oversized shared context backup 누적

현재 WSL 체크아웃에는 대형 `shared.md.oversized-*` 파일이 없다. 다만 이전 계측 경로에서는
oversized backup 하나가 `.trinity` 대부분을 차지했다. Trinity는 oversized `shared.md`를
감지하면 원본을 옮기고 작은 recovery projection을 만든다.

좋은 점:

- active `shared.md`를 계속 읽다가 앱이 멈추는 문제를 피한다.
- 원본을 보존해 복구 가능성을 남긴다.

위험:

- GB 단위 파일이 `.trinity` 안에 남아 workspace 전체 작업을 느리게 만들 수 있다.
- 여러 번 oversized가 발생하면 디스크 사용량이 빠르게 증가한다.
- 사용자는 active 파일이 작아졌는데도 프로젝트가 무겁다고 느낄 수 있다.

개선안:

- `/memory compact` 이후 oversized backup retention 안내를 UI에 표시한다.
- `/memory cleanup --oversized-backups` 명령을 추가한다. 기본은 dry-run이고,
  실제 삭제는 `--apply`를 명시한 경우에만 수행한다.
- retention 기본값을 둔다. 현재 구현 기준은 최신 1개 보관이며
  `--keep-latest N`으로 조정한다.
- backup manifest를 만들어 크기와 생성 시점을 report/settings에서 보여준다.
- 자동 삭제는 위험하므로 명시 명령과 dry-run 우선 흐름을 유지한다.

하네스:

- 2GB를 실제로 만들 필요 없이 sparse/fake size fixture 또는 낮은 max_read_bytes로 oversized를
  재현한다.
- backup 생성, recovery projection, cleanup 명령, manifest 업데이트를 검증한다.

### 2. Events JSONL 전체 로드

`WorkflowPersistence.load_events_for_workflow()`는 `load_events()`로 events 파일 전체를 읽고
workflow id로 filter한다. 현재는 events 447개라 아직 감당 가능하지만, 장기 workflow에서는 모든 snapshot,
report, resume/context 경로가 선형 비용을 갖는다.

현재 호출 지점:

- `NexusSnapshotAdapter.load_snapshot()`
- Textual report/context 관련 경로
- TUI session context 경로
- workflow engine recovery/audit 경로

위험:

- 0.25초 polling loop에서 snapshot이 자주 만들어지면 events 증가에 따라 UI가 끊길 수 있다.
- report screen 진입 시 같은 events를 반복 로드할 수 있다.
- resume 후 context 표시가 늦어지는 원인이 될 수 있다.

개선안:

- `WorkflowPersistence`에 events mtime/size 기반 in-process cache를 추가한다.
- `load_events_for_workflow(..., tail=N)`이 전체 JSONL을 다 parse하지 않도록 tail reader를 둔다.
- active workflow event offset을 기억해 incremental read를 지원한다.
- 장기적으로 workflow id별 event index 또는 archive manifest를 둔다.

우선순위:

- P1: mtime/size cache
- P2: tail reader
- P3: event index

하네스:

- events 5,000/50,000개 fixture로 snapshot load time을 측정한다.
- cache hit/miss를 분리해 검증한다.

### 3. Snapshot 반복 로드와 projection 비용

`NexusSnapshotAdapter.load_snapshot()`은 session, events, provider state, synthesis, questions,
decisions, central blueprint, WP details, review aggregation, execution recovery를 한 번에 만든다.

현재는 운영 가능한 수준이지만 다음 이유로 커질 수 있다.

- events 전체 load
- review_results를 매 snapshot마다 `ReviewResult.from_dict()`로 재구성
- work_packages와 execution_results/review_results join
- shared section read
- report/export 화면에서도 snapshot fallback 호출

개선안:

- snapshot memoization key를 둔다.
  - session `updated_at`
  - events file mtime/size
  - recent_events hash 또는 length
  - shared.md mtime/size
- active route별 필요한 projection만 lazy로 만든다.
  - Nexus: provider/central/questions/WP summary
  - Execution: work_package_details/execution_log
  - Report: full audit/review/action details
- heavy detail field는 row 선택 시 lazy load한다.

하네스:

- 같은 session에서 repeated `load_snapshot()` 호출이 cache hit되는지 검증한다.
- session/event/shared가 바뀌면 cache invalidation되는지 검증한다.
- WP 100개, review 300개 fixture에서 projection budget을 둔다.

### 4. Resume archive listing

`WorkflowPersistence.list_archives()`는 history directory의 archive JSON을 모두 읽고
`WorkflowSession.from_dict()`로 파싱한 뒤 updated_at으로 정렬한다.

현재 archive 28개 기준 평균 8ms라 문제는 작다. 하지만 수백 개가 되면 resume modal open이
느려질 수 있다.

개선안:

- archive 생성 시 summary manifest를 함께 갱신한다.
  - session id
  - goal
  - state
  - updated_at
  - path
  - event path
  - work package count
- resume list는 manifest만 읽는다.
- archive restore 시에만 full session JSON을 읽는다.
- manifest가 없거나 깨지면 lazy rebuild한다.

하네스:

- archive 1,000개 synthetic fixture 생성
- manifest path와 legacy fallback path latency 비교
- corrupted manifest fallback 검증

### 5. Model discovery timeout과 직렬 처리

Textual app은 provider model discovery worker를 시작하고, 각 configured agent에 대해
`discover_provider_models()`를 호출한다. 현재 app 쪽 timeout은 provider당 10초다.

위험:

- provider 3개가 모두 CLI 지연을 겪으면 최초 모델 목록 반영이 늦다.
- worker thread라 UI thread를 막지는 않지만, 사용자는 `/model` modal에서 fallback/old list를
  보게 된다.
- refresh가 직렬이면 가장 느린 provider가 전체 완료를 늦춘다.

개선안:

- 기존 cache 또는 static fallback을 즉시 표시하고 live discovery는 백그라운드에서 refresh한다.
- discovery timeout은 고정 3초가 아니라 provider별 기본값으로 분리한다. 예: 빠른 local list는
  3초, 느린 provider는 5~10초.
- provider별 discovery를 thread pool로 병렬 실행한다.
- modal은 provider별 loading/error/source를 표시한다.
- cache를 app lifetime뿐 아니라 `.trinity/provider-models.json` 같은 small cache로 저장한다.
- live discovery와 static fallback을 명확히 표시한다.

하네스:

- fake `codex debug models`, `agy models`에 delay를 넣는다.
- one provider timeout이 다른 provider 결과 표시를 막지 않는지 검증한다.
- selected model이 refresh 후에도 유지되는지 검증한다.

### 6. Execution partial result persistence

현재 엔진에는 `record_execution_results(..., finalize=False)`로 개별 WP 결과를 session에
upsert하는 경로가 있다. 다만 execution protocol/controller/report가 이 경로를 항상 같은 계약으로
사용한다는 보장이 약하다.

성능 문제라기보다 UX/관측성 문제지만, 사용자는 긴 실행 중에 "완료된 WP 보고서가 왜 안 보이지"라고
느끼게 된다. 사용자가 같은 화면을 반복 확인하면 체감상 더 느린 제품이 된다.

개선안:

- `execute_work_packages(..., result_callback=...)`를 Textual controller에서 실제 사용한다.
- callback에서 `workflow.record_execution_results([result], finalize=False)`를 호출한다.
- 완료 시 finalize만 수행한다.
- fallback attempt metadata도 partial result와 함께 저장한다. `codex/p2-p3-scalability-hardening`에서
  `ExecutionResult.attempt_chain`을 session/event/report/snapshot에 저장하도록 반영했다.

주의:

- background thread에서 workflow/session file write가 발생하므로 lock과 UI thread handoff 정책을
  분명히 해야 한다.
- event consume과 result callback이 같은 결과를 중복 기록하지 않도록 idempotent upsert를 유지한다.

하네스:

- WP-001 done, WP-002 running 상태에서 session.execution_results에 WP-001이 있는지 검증한다.
- Execution Matrix와 Report가 partial result를 보여주는지 검증한다.

### 7. Report and inspector lazy loading

Report와 inspector는 긴 raw output, JSON, event log, review details를 다룬다. 지금은 active
데이터가 작지만, provider raw artifact가 많아지면 report open 또는 tab switch가 무거워질 수 있다.

개선안:

- report 기본 화면은 summary만 로드한다.
- raw artifact body는 사용자가 펼칠 때 lazy read한다.
- JSON pretty formatting은 size threshold를 둔다.
- inspector all tab은 tail-first로 보여주고 full load는 명시 동작으로 분리한다.
- artifact manifest를 두어 path/stat/summary만 먼저 읽는다.

하네스:

- 5MB raw artifact fixture로 report open time과 expand time을 분리 측정한다.
- JSON pretty formatting threshold와 truncation 표시를 검증한다.

### 8. Textual polling/render pressure

Textual app은 workflow running 중 0.25초마다 controller를 poll한다. 이벤트가 없으면 activity
frame만 advance한다. 이벤트가 있으면 snapshot을 만들고 화면에 apply한다.

위험:

- snapshot build가 100ms 이상으로 커지면 0.25초 polling과 겹쳐 UI가 뻣뻣해질 수 있다.
- provider cards, central panel, execution matrix가 전체 re-render 위주면 변경이 작아도 비용이 크다.

개선안:

- snapshot cache를 먼저 넣는다.
- route별 apply diff를 강화한다.
- execution matrix는 row count가 많을 때 table body를 incremental update한다.
- activity animation은 workflow state 변경과 분리해 아주 가벼운 state만 바꾼다.

하네스:

- fake event burst 1,000개를 넣고 poll loop 처리 시간을 측정한다.
- WP 100개 matrix apply 시간을 측정한다.

### 9. Memory pack and context read

`SharedContextEngine.pack_context_for_prompt()`는 shared section을 읽고 memory recent record를
budget 안에서 packing한다. SQLite memory가 커질수록 index와 query pattern이 중요해진다.

개선안:

- memory table에 `workflow_id`, `kind`, `created_at` index가 있는지 확인한다.
- memory pack 결과를 workflow_id/kind/recent limit/DB mtime 기준으로 cache한다.
- provider prompt마다 같은 context를 다시 pack하지 않도록 round-level cache를 둔다.

하네스:

- memory record 10,000개 synthetic fixture
- workflow_id/kind filter latency 측정
- pack truncation과 pinned section 보존 검증

## 개선 우선순위

### P0: 성능 하네스와 계측

먼저 기준값을 만들지 않으면 최적화 효과를 확인하기 어렵다.

작업:

- `tests/harness/perf.py` 또는 `tests/perf/`에 synthetic fixture generator 추가
- session/events/archive/shared/memory size별 계측 함수 추가
- CI에서는 smoke threshold만, local에서는 상세 metric 출력

완료 기준:

- snapshot, resume, execute-retry, report, model discovery, memory pack의 baseline을 출력한다.
- PR마다 before/after를 비교할 수 있다.

### P1: 저위험 빠른 개선

작업:

- workflow events mtime/size cache
- snapshot memoization
- route별 projection cache key 명시
- model discovery는 캐시 결과를 즉시 표시하고 live refresh를 백그라운드에서 병렬 실행
- model discovery timeout은 고정 3초가 아니라 provider별 기본값으로 분리

예상 효과:

- running 중 UI polling 부담 감소
- `/model` modal 체감 개선
- resume/report/snapshot 성장 비용 완화

### P2: UX와 관측성 개선

작업:

- execution partial result persistence
- fallback attempt chain persistence: `codex/p2-p3-scalability-hardening`에서
  fallback 성공/전체 실패의 agent/status/summary/blocker/raw artifact path를 session,
  workflow events, report markdown, Textual WP detail projection에 남기도록 구현했다.
- report raw artifact lazy loading: `codex/p2-p3-scalability-hardening`에서 snapshot
  artifact preview를 bounded byte read로 변경했다.
- inspector tail-first rendering
- archive summary manifest: `codex/p2-p3-scalability-hardening`에서
  `.trinity/workflow/history/manifest.json` 기반 resume 목록 로딩을 추가했다.
- oversized backup cleanup 명령과 retention 표시

예상 효과:

- 긴 WP 실행 중에도 보고서와 Execution Matrix가 바로 업데이트된다.
- fallback 원인 분석이 UI에서 가능해진다.
- report 화면이 큰 artifact에 덜 끌려간다.
- 대형 `.trinity` artifact가 재발해도 사용자가 원인과 정리 방법을 확인할 수 있다.

### P3: 구조적 확장성 개선

작업:

- workflow event index: `codex/p2-p3-scalability-hardening`에서
  `.trinity/workflow/events.index.jsonl` offset index와 stale rebuild를 추가했다.
- report/audit artifact manifest
- route별 lazy projection
- memory pack cache
- 대형 review aggregation index

예상 효과:

- 장기 workflow와 archive가 많아져도 resume/report/Nexus가 안정적으로 유지된다.

## 권장 acceptance budget

초기 성능 목표:

| Operation | 목표 |
| --- | ---: |
| app startup to first screen | 500ms 이하, provider discovery 제외 |
| cached `/model` modal open | 50ms 이하 |
| live model discovery visible first result | provider별 3초 이내 |
| active snapshot load, events 5,000개 | 100ms 이하 |
| active snapshot load, WP 100개/review 300개 | 150ms 이하 |
| `/resume` archive list, 1,000개 | 150ms 이하 |
| `/execute-retry` plan, WP 100개 | 50ms 이하 |
| report summary open, artifact 100개 | 150ms 이하 |
| raw artifact expand, 5MB | 300ms 이하 또는 명시 loading |
| memory pack, record 10,000개 | 150ms 이하 |

## 바로 실행 가능한 다음 작업

1. performance harness skeleton 추가
2. current-state 계측 fixture와 large-session fixture 추가
3. events cache와 snapshot memoization 구현
4. model discovery cache-first UI와 provider별 병렬화 구현
5. execution partial result의 UI/report 통합 계약 고정
6. report/inspector lazy loading 구현
7. `shared.md.oversized-*` retention/cleanup 설계와 명령 추가

현재 체감 렉의 직접 원인은 상황마다 다를 수 있다. 하지만 위 순서대로 진행하면 "큰 파일 때문에
무거운 문제", "반복 snapshot 때문에 끊기는 문제", "provider discovery 때문에 늦게 채워지는 문제",
"긴 실행 중 보고서가 안 보이는 문제"를 모두 계측 가능한 형태로 줄일 수 있다.

## 최종 판단

Trinity는 workflow 기능이 빠르게 복잡해졌고, 이제 성능 병목도 단일 함수가 아니라 persisted state,
event replay, artifact 관리, Textual projection, provider discovery가 함께 만드는 문제가 될 가능성이
높다.

현재 수치만 보면 active workflow는 아직 운영 가능한 수준이다. 그러나 session과 snapshot 비용이 이미
커지고 있고, event/archive/snapshot 구조가 선형 로드에 기대고 있으므로 장기 사용에서는 같은 유형의
렉이 반복될 수 있다. oversized backup은 현재 체크아웃에서는 재현되지 않았지만, 과거 계측처럼 GB 단위
artifact가 남는 상황을 막기 위한 retention/cleanup 정책은 별도 운영 기능으로 필요하다.

따라서 성능개선은 먼저 하네스로 재현 가능한 상태를 만들고, 그 다음 cache/index/lazy loading/retention
정책을 순서대로 적용하는 것이 가장 안전하다.
