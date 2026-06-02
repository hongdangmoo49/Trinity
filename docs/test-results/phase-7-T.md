# Phase 7 Test Results — Prompt Compression

> 2026-06-02

## 요약

| 항목 | 값 |
|------|-----|
| 총 테스트 수 | **640** |
| 통과 | **640** |
| 실패 | 0 (기존 1개 test_retry.py jitter 버그 제외 — Phase 7 무관) |
| 신규 테스트 | **18** (Phase 7) |
| 실행 시간 | ~19s |
| 환경 | macOS Darwin 25.5.0, Python 3.14 |

---

## 신규 테스트 파일

### 1. `tests/test_compressor.py` — 8 tests

휴리스틱 텍스트 압축기 (`trinity.context.compressor`) 테스트.

| 테스트 | 설명 |
|--------|------|
| `test_compress_single_opinion_extracts_key_points` | 단일 의견에서 핵심 문장 추출, pytest 키워드 보존 확인 |
| `test_compress_multiple_opinions` | 다중 에이전트 의견 압축, 에이전트명 또는 핵심 내용 보존 |
| `test_compress_empty_opinions_returns_empty` | 빈 입력에 대해 빈 문자열 반환 |
| `test_compress_preserves_agreement_disagreement` | AGREE/DISAGREE 합의 감지 키워드 보존 |
| `test_compress_short_text_unchanged` | 예산 내 짧은 텍스트는 변경 없이 반환 |
| `test_compress_opinions_formats_with_agent_names` | 에이전트별 `**name**:` 라벨 포맷 확인 |
| `test_estimated_token_count` | 토큰 추정치 > 0 및 < 텍스트 길이 |
| `test_compress_respects_max_tokens` | 압축 결과가 max_summary_tokens 초과하지 않음 (±20% 허용) |

### 2. `tests/test_protocol_compression.py` — 5 tests

프로토콜 통합 (`trinity.deliberation.protocol`) 테스트.

| 테스트 | 설명 |
|--------|------|
| `test_round_1_no_compression` | Round 1은 이전 라운드 참조 없음 |
| `test_round_2_verbatim_previous` | Round 2는 Round 1 전체 텍스트 포함 (압축 없음) |
| `test_round_3_uses_compressed_old_rounds` | Round 3+은 압축된 요약 + 직전 라운드 verbatim |
| `test_compression_disabled` | 비활성화 시 기존 동작과 동일하게 verbatim만 사용 |
| `test_prompt_size_reduction` | 압축 활성화 시 프롬프트 크기 실제 감소 확인 |

### 3. `tests/test_config.py` 추가 — 1 test

압축 설정 필드 (`trinity.config`) 테스트.

| 테스트 | 설명 |
|--------|------|
| `test_config_compression_defaults` | 기본값: enabled=True, threshold=2, max_tokens=200 |

### 4. `tests/test_shared_context.py` 추가 — 3 tests

압축 섹션 저장 (`trinity.context.shared`) 테스트.

| 테스트 | 설명 |
|--------|------|
| `test_write_compressed_summary` | 압축된 라운드 요약을 "Round N Summary" 섹션에 저장 |
| `test_get_rounds_for_prompt_includes_compressed` | 압축 요약 + verbatim 최신 라운드 혼합 반환 |
| `test_get_rounds_for_prompt_no_compression` | verbatim_rounds 충분 시 압축 없이 전체 반환 |

### 5. `tests/test_orchestrator.py` 추가 — 1 test

설정 전달 (`trinity.orchestrator`) 테스트.

| 테스트 | 설명 |
|--------|------|
| `test_orchestrator_passes_compression_config` | TrinityConfig → Protocol 압축 설정 전달, 비활성화 시 compressor=None |

---

## 신규 모듈

### `src/trinity/context/compressor.py` — 244줄

| 메서드 | 설명 |
|--------|------|
| `estimate_tokens(text)` | 영어 ~1.3 tok/word, CJK ~1.5 tok/char 추정 |
| `compress_heuristic(text)` | 문장 분리 → 키워드 점수 → 상위 문장 예산 내 선택 |
| `compress_opinions_heuristic(opinions)` | 에이전트별 예산 분배 후 개별 압축 + 라벨링 |
| `_score_sentences(sentences)` | 키워드 밀도 + 위치(첫/끝 문장 가중치) + 길이 점수 |
| `_truncate_to_budget(text)` | 예산 초과 시 단어 단위 잘림 + "..." |

---

## 변경된 기존 파일

| 파일 | 변경 내용 |
|------|-----------|
| `config.py` | 3개 데이터클래스 필드 + TOML 파서 3줄 추가 |
| `context/shared.py` | `write_compressed_summary()`, `get_rounds_for_prompt()` 메서드 추가 |
| `deliberation/protocol.py` | `__init__` 3개 파라미터, `_build_round_prompt()` 압축 로직, `_compress_old_rounds()`, `_extract_agent_opinions()` 추가 |
| `orchestrator.py` | Protocol 생성자에 3개 compression 키워드 인자 전달 |

---

## 발견된 이슈

| 항목 | 설명 | 상태 |
|------|------|------|
| `test_retry.py::test_capped_at_max_delay` 기존 실패 | jitter가 max_delay를 약간 초과 (5.43 > 5.0) | Phase 7 무관, 기존 이슈 |

---

*작성일: 2026-06-02*
