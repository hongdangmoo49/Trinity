# Trinity v1.0 텔레그램 홍보 글

## 짧은 버전

Trinity v1.0을 준비하고 있습니다.

Trinity는 Claude Code, Codex, Antigravity CLI를 하나의 작업 흐름으로 묶는 멀티 에이전트 오케스트레이터입니다.

사용자는 목표와 작업공간만 정하면 됩니다. Trinity는 목표를 work package로 나누고, 에이전트별 역할에 맞춰 병렬 실행한 뒤, 결과를 리뷰하고 실패 지점은 재시도할지 물어봅니다.

이제 단순히 여러 AI를 번갈아 쓰는 것이 아니라, 하나의 컨텍스트에서 설계, 구현, 리뷰, 재시도까지 이어갈 수 있습니다.

GitHub:
https://github.com/hongdangmoo49/Trinity

설치:
```bash
python -m pip install --upgrade trinity-agent
trinity init
trinity
```

## 긴 버전

Trinity v1.0을 준비하고 있습니다.

요즘 AI 코딩 도구는 강력하지만, 실제 프로젝트에서는 이런 일이 자주 생깁니다.

- 설계는 Claude에게 물어보고
- 구현은 Codex에게 맡기고
- 다른 관점의 리뷰는 Antigravity에게 확인하고
- 결과를 다시 사람이 붙여 맞추고
- 실패한 작업은 어디서부터 재시도해야 할지 직접 판단합니다

Trinity는 이 흐름을 하나의 작업대로 묶는 도구입니다.

사용자는 목표를 입력하고 작업공간을 선택합니다. 그러면 Trinity가 목표를 work package로 나누고, 각 에이전트의 역할에 맞춰 병렬로 실행합니다. 작업이 끝나면 결과를 모으고, 리뷰가 필요한 지점이나 실패한 provider가 있으면 바로 집계하지 않고 사용자에게 다음 선택을 묻습니다.

핵심은 “AI 세 개를 동시에 켜는 것”이 아니라 “하나의 목표, 하나의 컨텍스트, 하나의 실행 흐름”입니다.

Trinity v1.0에서 보고 있는 방향은 다음과 같습니다.

- 현재 폴더 기반의 자연스러운 실행 흐름
- target workspace 선택과 실행 전 preflight
- Claude, Codex, Antigravity 역할 기반 병렬 실행
- work package 단위 진행 상태와 리뷰 흐름
- provider 오류 발생 시 재시도, 제외 후 계속, 중단 선택
- 실행 실패 후 복구 가능한 패키지 재시도
- PyPI 기반 업데이트 안내

설치:
```bash
python -m pip install --upgrade trinity-agent
trinity init
trinity
```

GitHub:
https://github.com/hongdangmoo49/Trinity

홍보 이미지:
`docs/assets/promo/trinity-user-workflow-ko.svg`

한 줄로 말하면, Trinity는 AI 코딩 에이전트들을 “각자 대답하는 도구”에서 “함께 일하는 팀”으로 바꾸려는 시도입니다.
