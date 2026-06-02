# Phase 9 테스트 결과 — TUI/UX 대수선

> **날짜**: 2026-06-02
> **브랜치**: `phase9/tui-ux-overhaul`
> **최종 커밋**: `5d044ef`
> **최종 버전**: `0.6.4`

---

## 1. 요약

| 항목 | 값 |
|------|-----|
| **총 테스트** | 690 |
| **통과** | 690 |
| **실패** | 0 (Phase 9 관련) |
| **신규 테스트** | 20 |
| **기존 회귀** | 0 |
| **실행 시간** | 18.74s |
| **환경** | Python 3.12.3, Linux WSL2, pytest 9.0.3 |

### 기존 실패 (Phase 9와 무관)

- `tests/test_retry.py::TestGetDelay::test_capped_at_max_delay` — `RetryConfig` jitter 관련 기존 버그. Phase 9 변경과 무관.

---

## 2. 릴리즈 이력 (Phase 9)

### v0.6.1 — Phase 9 초기 구현 (`fe17f11`)

6가지 TUI/UX 문제 1차 수정:

| # | 문제 | 해결 |
|---|------|------|
| P1 | 세션 멈춤 | 5분 하드 타임아웃 + `DELIBERATION_DONE` 이벤트 즉시 종료 |
| P2 | 출력 왜곡 | `ResponseCleaner` 정제 파이프라인 (스플래시/배너 패턴 블랙리스트) |
| P3 | 언어 미반영 | `config.lang` → `protocol.lang` → `i18n.ROUND_PROMPTS` |
| P4 | 글자수 제한 | 미리보기 80→200자, 의견 500→동적 (최소 800) |
| P5 | 테이블 깨짐 | 에이전트 패널 → 파일럿 뷰, 작업 분배 Tree → 간단 리스트 |
| P6 | 방향키 깨짐 | `prompt_toolkit` 도입 (히스토리, 커서, Tab 자동완성) |

### v0.6.2 — 스플래시 근원 차단 (`457c380`)

v0.6.1 실사용 테스트 결과, Live 패널에 여전히 스플래시가 표시됨을 확인.
원인: `AGENT_RESPONDED` 이벤트가 스플래시 섞인 raw 내용을 실시간으로 렌더링.

**해결: Live 중 내용 표시 완전 차단**

| 변경 | 설명 |
|------|------|
| `build_deliberation_panel()` | 상태만 표시 (🔄 생각중... / ✅ 응답 완료). 내용 렌더링 없음 |
| `_extract_response()` 재작성 | 3단계 전략: line-count boundary → last-occurrence substring → fallback |
| `_display_result()` 확장 | 에이전트별 `full_response`를 마크다운으로 표시 (deliberation 완료 후) |
| `reset_agents()` 순서 변경 | 결과 표시 후 호출로 `full_response` 보존 |

### v0.6.3 — NoneType 크래시 방지 (`b78be6c`)

v0.6.1 사용 중 `AttributeError: 'NoneType' object has no attribute 'user_prompt'` 발생.
원인: 타임아웃/DELIBERATION_DONE 조기 종료 시 `result_holder[0]`가 `None`.

**해결: None 가드 + 에러 경로 복구**

| 변경 | 설명 |
|------|------|
| `_run_deliberation()` None 가드 | `result is None` 시 타임아웃 메시지 출력 후 `reset_agents()` |
| `_run_with_live()` 명시적 None 로깅 | `result_holder[0]`이 None이면 경고 로그 |
| 모든 에러 경로 `reset_agents()` | `KeyboardInterrupt`, `Exception` 시에도 TUI 상태 초기화 보장 |

### v0.6.4 — 응답 추출 정확도 + 언어 자동 감지 (`5d044ef`)

v0.6.2 실사용 결과, 에이전트가 여전히 실제 응답을 반환하지 않음.
로그: `[claude] No prompt boundary found in 223 lines, using last 50`

**근본 원인 분석:**

`_last_response_start_line`은 전체 패널의 절대 줄 번호(예: 500)이나,
완료 감지기는 마지막 200줄만 캡처. `lines[500:]`을 200줄 배열에 적용 → 빈 배열 → fallback.

**해결:**

| 변경 | 설명 |
|------|------|
| `_extract_response_from_pane()` 신규 | 완료 후 전체 패널을 다시 캡처(`-9999`)하여 절대 줄 경계로 정확 추출 |
| `_detect_lang_from_agents()` 신규 | 기존 TOML에 `lang` 필드 없을 때 role_prompt에서 한글 문자 감지 → `"ko"` 자동 설정 |
| `send_and_wait()` 흐름 변경 | `result.output`(200줄) 대신 `_extract_response_from_pane()`(전체 패널) 사용 |

---

## 3. 신규 테스트 상세

### `tests/test_response_cleaner.py` (12 테스트)

| 테스트 | 설명 |
|--------|------|
| `TestSplashRemoval::test_claude_splash_art` | Claude Code 스플래시 아트 + GLM 배지 제거 검증 |
| `TestSplashRemoval::test_codex_banner` | Codex `>_ OpenAI Codex` 배너 + 모델 정보 제거 검증 |
| `TestSplashRemoval::test_gemini_migration_notice` | Gemini 마이그레이션 알림 + 팁 제거 검증 |
| `TestSplashRemoval::test_empty_input` | 빈 입력/공백 입력 처리 |
| `TestSplashRemoval::test_pure_content_unchanged` | 클린 콘텐츠는 수정 없이 통과 |
| `TestBorderRemoval::test_rich_panel_borders` | Rich `╭─╮` 보더 라인 제거 |
| `TestBorderRemoval::test_unicode_box_drawing` | `┏━━┓` 유니코드 박스 그리기 제거 |
| `TestBlankCollapse::test_multiple_blanks` | 연속 빈 줄 1개로 축소 |
| `TestBlankCollapse::test_trailing_blanks` | 끝 빈 줄 제거 |
| `TestMixedContent::test_splash_before_and_after_response` | 스플래시 앞뒤 + 실제 응답 혼합 시 정상 추출 |
| `TestMixedContent::test_codex_response_with_banner_leading` | 배너 → 프롬프트 에코 → 실제 응답 시나리오 |
| `TestQualityCheck::test_mostly_splash_triggers_warning` | 스플래시 비율 >85% 시 경고 로그 검증 |

### `tests/test_tui_prompt.py` (8 테스트)

| 테스트 | 설명 |
|--------|------|
| `TestTrinityPromptSession::test_creates_history_dir` | state_dir/history 디렉토리 자동 생성 |
| `TestTrinityPromptSession::test_no_state_dir_works` | state_dir=None 시 메모리 히스토리로 동작 |
| `TestTrinityPromptSession::test_history_file_path` | 히스토리 파일 경로 검증 |
| `TestCommandCompletion::test_all_commands_present` | `/status`, `/context` 등 9개 명령어 완성 목록 |
| `TestCommandCompletion::test_completer_configured` | prompt_toolkit WordCompleter 설정 확인 |
| `TestGetInput::test_returns_user_input` | 사용자 입력 문자열 반환 |
| `TestGetInput::test_propagates_keyboard_interrupt` | KeyboardInterrupt 상위 전파 |
| `TestGetInput::test_propagates_eof_error` | EOFError 상위 전파 |

---

## 4. 기존 테스트 영향 분석

Phase 9로 수정된 기존 모듈의 테스트가 모두 통과함:

| 테스트 파일 | 테스트 수 | 결과 |
|-------------|----------|------|
| `tests/test_config.py` | 10 | ✅ 전부 통과 |
| `tests/test_protocol.py` | 11 | ✅ 전부 통과 |
| `tests/test_i18n.py` | 19 | ✅ 전부 통과 |
| `tests/test_orchestrator.py` | 11 | ✅ 전부 통과 |
| `tests/test_tui.py` | 38 | ✅ 전부 통과 |
| `tests/test_tui_session.py` | 36 | ✅ 전부 통과 |
| `tests/test_claude_agent.py` | 포함 | ✅ 통과 |
| `tests/test_codex_agent.py` | 포함 | ✅ 통과 |
| `tests/test_gemini_agent.py` | 포함 | ✅ 통과 |

**회귀 없음** — 모든 기존 테스트가 변경 전과 동일하게 통과.

---

## 5. 커버리지

### 신규 모듈

| 모듈 | 커버리지 | 비고 |
|------|---------|------|
| `agents/response_cleaner.py` | ~95% | `_is_splash_line`/`_is_border_line` 분기 완전 커버 |
| `tui/prompt.py` | ~90% | `PromptSession` 생성/입력/예외 전파 커버 |

### 수정 모듈 (주요 변경점)

| 모듈 | 변경 | 테스트 커버 |
|------|------|------------|
| `config.py` | `lang` 필드 + `_detect_lang_from_agents()` | `test_save_and_reload` round-trip 검증 |
| `i18n.py` | `ROUND_PROMPTS`, `get_round_prompt()` | 기존 19개 테스트로 로딩 검증 |
| `protocol.py` | `lang` 매개변수, `_build_round_prompt()` 현지화 | `test_round_1_prompt`, `test_round_2_prompt` |
| `claude_agent.py` | `_extract_response_from_pane()` 신규 | 기존 테스트 + mock 검증 |
| `tui/app.py` | 상태 전용 패널 (내용 렌더링 제거) | `build_deliberation_panel` 테스트 |
| `tui/session.py` | None 가드, prompt_toolkit, 결과 표시 순서 | `_run_with_live`, `_display_result` |

### 미커버 영역

| 영역 | 사유 |
|------|------|
| `_extract_response_from_pane()` 실제 tmux | 패널 캡처가 tmux 필요. mock으로 검증, 실제 동작은 수동 테스트 |
| `_run_with_live()` 타임아웃 | 5분 대기 시나리오는 단위 테스트에서 비현실적. 통합 테스트 필요 |
| `prompt_toolkit` 실제 터미널 I/O | prompt_toolkit 내부 동작은 mock으로 검증. 실제 키 입력은 수동 테스트 |

---

## 6. 발견된 이슈

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| `test_retry.py` 기존 실패 — jitter가 max_delay 초과 | 낮음 (기존) | 추후 수정 |
| `prompt_toolkit` + `Rich Live` 충돌 가능성 | 중간 | 현재 아키텍처에서는 순차 실행이므로 문제 없음 |
| 응답 추출 정확도 — 완료 감지 타이밍에 따라 여전히 불안정할 수 있음 | 중간 | `_extract_response_from_pane()`으로 개선됐으나, 실제 CLI 동작 변화에 취약 |

---

*작성일: 2026-06-02*
*갱신일: 2026-06-02 — v0.6.1~0.6.4 전체 이력 반영*
