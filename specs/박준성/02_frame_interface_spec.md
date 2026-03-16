# Frame Interface 명세

## 1. 목적

본 문서는 AI 가속기 입력 frame과 출력 result의 비트 수준 구조를 정의한다.

## 2. 입력 frame 구조

| 필드명 | 비트 폭 | 설명 |
|---|---:|---|
| frame_id | 32 | frame 식별자 |
| x_hist | 24 | X-path 입력용 detector history |
| z_hist | 24 | Z-path 입력용 detector history |
| decoder_mode | 2 | 0: normal, 1: debug, 2: single-path, 3: reserved |
| confidence_threshold | 8 | confidence cutoff |
| model_version | 8 | weight set 버전 |

총 입력 길이는 98-bit이며, 구현 시 128-bit aligned packet으로 패딩할 수 있다.

## 3. 출력 result 구조

| 필드명 | 비트 폭 | 설명 |
|---|---:|---|
| frame_id | 32 | 입력 식별자 |
| corr_x_mask | 9 | X-path correction mask |
| corr_z_mask | 9 | Z-path correction mask |
| score_x | 16 | X-path confidence |
| score_z | 16 | Z-path confidence |
| latency_cycles | 16 | 처리 cycle |
| status_flags | 8 | done, error, threshold_reject 등 |

## 4. 핸드셰이크 규약

| 신호 | 방향 | 의미 |
|---|---|---|
| in_valid | Host -> FPGA | 입력 frame 유효 |
| in_ready | FPGA -> Host | 입력 수신 가능 |
| out_valid | FPGA -> Host | 출력 result 유효 |
| out_ready | Host -> FPGA | 출력 수신 완료 |

## 5. 예외 처리 규칙

| 상황 | 처리 |
|---|---|
| 입력 누락 | error flag 세트 |
| 지원하지 않는 model_version | reject 처리 |
| timeout | status_flags에 timeout 기록 |