# PromptComposer 렌더 키 재바인딩 보강

- 브랜치: `perf/prompt-composer-render-key-rebind`
- 버전: `1.0.292` -> `1.0.293`
- 대상: `src/trinity/textual_app/widgets/composer.py`

## 배경

`PromptComposer`는 Start/Nexus 입력창에서 slash command palette를 렌더한다. 입력 중 반복 렌더 비용을 줄이기 위해 palette 전체 render key, option row key, more indicator key, palette visibility key를 저장하고 같은 상태의 DOM mutation을 건너뛴다.

하지만 `refresh(recompose=True)` 이후에는 text area, palette, option row, more indicator 위젯이 새로 만들어진다. 기존 compose 경로는 위젯 참조만 초기화하고 render key는 유지했기 때문에, 같은 slash query가 다시 입력되면 새 option row가 빈 상태인데도 `_render_command_options()`와 `_set_command_palette_visible()`이 스킵될 수 있다.

## 개선안

1. compose 시작 시 고정 위젯 캐시와 함께 palette render cache를 초기화한다.
2. `_command_options_key`, `_command_option_row_keys`, `_command_more_key`, `_command_palette_visible_key`를 새 DOM 기준으로 리셋한다.
3. 리컴포즈 후 같은 slash query를 다시 입력해도 command option row가 다시 채워지는지 테스트한다.

## 기대 효과

- PromptComposer 재구성 후 slash command palette가 빈 상태로 남는 문제를 방지한다.
- 입력 상태와 matching 로직은 유지하면서 DOM mutation skip cache만 새 위젯 생명주기에 맞춘다.
- Nexus/Start 공통 입력 컴포넌트의 캐시 수명주기를 다른 Textual 위젯과 일관되게 맞춘다.
