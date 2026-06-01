# Phase 3-T 테스트 결과 보고서

> Phase 3 Context 모니터링 + 자동 세션 교체 테스트 — 2026-06-01

---

## 요약

| 항목 | 결과 |
|------|------|
| **총 테스트 수** | 234 |
| **통과** | 234 |
| **실패** | 0 |
| **전체 커버리지** | 94% |
| **실행 시간** | 4.73s |
| **환경** | Python 3.14.0, Windows 11, pytest 9.0.3, pytest-asyncio 1.4.0 |

---

## 기존 테스트 (190개)

Phase 1~2-T에서 작성된 190개 테스트. Phase 3 코드에 영향받지 않고 전부 통과.

---

## Phase 3-T 신규 테스트 (44개 추가)

### test_context_monitor.py — 17개 테스트

`src/trinity/context/monitor.py` (ContextMonitor) 커버. **98% 커버리지.**

| 테스트 클래스 | 테스트 | 설명 |
|-------------|--------|------|
| `TestProviderContextLimits` | `test_default_limits` | Provider별 기본 context 한계 |
| | `test_unknown_provider_returns_default` | 알 수 없는 Provider → 200K |
| `TestContextMonitorCheckUsage` | `test_no_rotation_needed` | 25% → 회전 불필요 |
| | `test_rotation_needed_at_threshold` | 60% → 회전 필요 |
| | `test_rotation_needed_above_threshold` | 75% → 회전 필요 |
| | `test_multiple_agents_partial_rotation` | 일부만 회전 필요 |
| | `test_all_need_rotation` | 전체 회전 필요 |
| | `test_custom_threshold` | 커스텀 임계값 (20%) 적용 |
| | `test_get_all_usage` | 전체 에이전트 사용량 조회 |
| `TestContextMonitorUpdateUsage` | `test_update_usage` | 수동 사용량 업데이트 |
| | `test_update_usage_with_total` | total 포함 업데이트 |
| | `test_update_nonexistent_agent` | 없는 에이전트 → 안전 |
| `TestContextMonitorParseUsage` | `test_parse_claude_json` | Claude JSON usage 파싱 |
| | `test_parse_claude_json_empty_usage` | 빈 usage → 업데이트 없음 |
| | `test_parse_codex_session` | Codex 세션 JSON 파싱 |
| | `test_parse_gemini_output` | Gemini CLI 출력 파싱 |
| | `test_parse_gemini_output_no_tokens` | 토큰 정보 없음 → 업데이트 없음 |

### test_session_rotator.py — 10개 테스트

`src/trinity/context/rotator.py` (SessionRotator) 커버. **96% 커버리지.**

| 테스트 클래스 | 테스트 | 설명 |
|-------------|--------|------|
| `TestSessionRotatorRotate` | `test_full_rotation_flow` | 전체 교체 플로우 (요약→종료→재시작) |
| | `test_summary_saved_to_shared` | shared.md Session History에 요약 기록 |
| | `test_continuation_includes_role` | 새 세션에 역할 프롬프트 포함 |
| | `test_rotation_failure_recovers` | 실패 시 에이전트 재시작 복구 |
| | `test_nonexistent_agent_returns_false` | 없는 에이전트 → False |
| `TestSessionRotatorTracking` | `test_rotation_count` | 교체 횟수 추적 |
| | `test_no_rotation_count_initially` | 초기 카운트 0 |
| | `test_get_all_rotation_counts` | 전체 카운트 조회 |
| `TestSessionRotatorBroadcast` | `test_broadcast_message` | 브로드캐스트 메시지 생성 |
| | `test_broadcast_first_rotation` | 첫 교체 시 count=0 |

### test_session_handoff.py — 5개 테스트

`SharedContextEngine.get_context_for_rotation()` 세션 핸드오프 검증.

| 테스트 클래스 | 테스트 | 설명 |
|-------------|--------|------|
| `TestKeepSectionsPreservation` | `test_pinned_sections_in_rotation_context` | pinned 섹션 보존 |
| | `test_recent_rounds_in_rotation_context` | 최근 N라운드만 포함 |
| | `test_session_history_in_rotation_context` | 세션 히스토리 포함 |
| | `test_empty_rotation_context` | 빈 컨텍스트 처리 |
| | `test_all_pinned_sections_preserved` | 모든 pinned 섹션 보존 |

### test_consensus_v2.py — 12개 테스트

`src/trinity/deliberation/consensus.py` (ConsensusEngine v2 — 부정어 필터링) 커버. **100% 커버리지.**

| 테스트 클래스 | 테스트 | 설명 |
|-------------|--------|------|
| `TestNegationFiltering` | `test_disagree_not_counted_as_agree` | "disagree" → 동의 아님 |
| | `test_dont_agree_not_counted` | "don't agree" → 동의 아님 |
| | `test_do_not_agree_not_counted` | "do not agree" → 동의 아님 |
| | `test_not_agree_not_counted` | "not agree" → 동의 아님 |
| | `test_mixed_negation_and_agreement` | 한 문장 부정 + 다른 문장 동의 → 동의 인정 |
| | `test_oppose_not_counted` | "oppose" → 동의 아님 |
| | `test_against_not_counted` | "against" → 동의 아님 |
| | `test_pure_agreement_still_works` | 순수 동의 → 정상 감지 |
| | `test_korean_agreement` | 한국어 동의 → 정상 감지 |
| `TestConsensusWithNegationInMultiAgent` | `test_disagree_false_positive_eliminated` | **핵심 버그 수정**: "disagree"가 "agree"로 매칭되던 문제 해결 |
| | `test_two_agree_one_disagrees_with_consensus` | 2/3 동의 → 합의 도달 |
| | `test_all_disagree` | 전원 반대 → 합의 없음 (0/3) |

---

## 커버리지 상세

### Phase 3 신규 모듈

| 모듈 | 문 | 미커버 | 커버리지 | 비고 |
|------|---|--------|---------|------|
| `context/monitor.py` | 61 | 1 | **98%** | L83: update_usage 로깅 |
| `context/rotator.py` | 53 | 2 | **96%** | L59-60: 재시작 실패 로깅 |
| `context/shared.py` | 105 | 1 | **99%** | 세션 핸드오프 개선 |
| `deliberation/consensus.py` | 45 | 0 | **100%** | 부정어 필터링 완전 커버 |

### 전체 프로젝트

| 지표 | 수치 |
|------|------|
| **총 문장** | 1288 |
| **미커버** | 82 |
| **전체 커버리지** | **94%** |

---

## 발견된 이슈 및 수정

| 이슈 | 설명 | 수정 |
|------|------|------|
| **"disagree" false positive** | ConsensusEngine이 "disagree"에서 "agree" 키워드를 매칭 | 부정어 패턴 14개 추가, 문장 단위 독립 판정 |
| **ContextMonitor 임계값 무시** | `check_usage()`가 `ContextUsage.should_rotate`(60% 고정)만 사용 | `usage.ratio >= self.rotate_threshold`로 직접 비교 |
| **mock `_update_usage` 시그니처 불일치** | 테스트 mock이 positional arg로 받아 keyword call과 충돌 | `FakeAgent` 실제 클래스로 교체 |

---

## 해결된 아키텍처 부채

| 부채 | 해결 내역 |
|------|-----------|
| ~~키워드 합의 판정~~ | ✅ 부정어 필터링으로 "disagree" false positive 제거 |
| ~~세션 교체 미구현~~ | ✅ ContextMonitor + SessionRotator 자동 교체 구현 |

---

*생성일: 2026-06-01*
*실행 환경: Windows 11, Python 3.14.0, pytest 9.0.3 + pytest-asyncio 1.4.0 + pytest-cov 7.1.0*
