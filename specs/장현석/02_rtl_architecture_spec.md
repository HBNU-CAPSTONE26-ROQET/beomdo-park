# AI 가속기 RTL 아키텍처 상세 명세

## 1. 목적

본 문서는 12-16-10 정책망을 수행하는 fixed-point neural inference engine의 RTL 블록 구조를 상세히 정의한다.

## 2. 데이터패스 구조

| 블록 | 입력 | 출력 | 설명 |
|---|---|---|---|
| syndrome_buffer | x_hist, z_hist | feature source | 입력 history 저장 |
| feature_formatter | 12-bit history | 12 x INT8 vector | bit to INT8 변환 |
| weight_memory | addr | weight/bias | layer별 계수 제공 |
| pe_array | feature, weight | partial sums | 병렬 MAC 수행 |
| accumulation_unit | partial sums, bias | neuron output | 뉴런별 누산 |
| activation_unit | neuron output | hidden vector | ReLU 및 saturation |
| threshold_unit | logits | correction mask | bitwise threshold 적용 |
| output_formatter | correction mask | aligned output | 9-bit mask 정렬 |

## 3. Layer 실행 순서

1. 선택된 path의 12개 feature를 formatter에 적재한다.
2. FC1 16개 뉴런을 대상으로 weight memory를 순차 스캔한다.
3. activation 결과를 hidden buffer에 저장한다.
4. FC2 10개 뉴런의 logits를 계산한다.
5. bitwise threshold와 confidence를 산출한다.
6. output formatter가 correction mask를 정렬한다.

## 4. PE Array 가정

| 항목 | 값 |
|---|---|
| PE 수 | 8 |
| 입력 폭 | 8-bit |
| weight 폭 | 8-bit |
| 곱셈 결과 | 16-bit |
| 누산 폭 | 16-bit 이상 |

## 5. 내부 버퍼

| 버퍼 | 크기 | 용도 |
|---|---|---|
| input_feature_buffer | 12 x 8-bit | 현재 path 입력 저장 |
| hidden_buffer | 16 x 8-bit | FC1 출력 저장 |
| logit_buffer | 10 x 16-bit | FC2 출력 저장 |

## 6. 제어 FSM 상태

| 상태 | 설명 |
|---|---|
| IDLE | 입력 대기 |
| LOAD_X | X-path feature 적재 |
| RUN_X_FC1 | X-path FC1 실행 |
| RUN_X_FC2 | X-path FC2 실행 |
| LOAD_Z | Z-path feature 적재 |
| RUN_Z_FC1 | Z-path FC1 실행 |
| RUN_Z_FC2 | Z-path FC2 실행 |
| WRITE_OUT | 결과 기록 |
| DONE | 완료 상태 |

## 7. 설계 원칙

1. 하나의 PE array를 X-path와 Z-path가 공유하여 자원을 절감한다.
2. weight memory는 layer별 bank 구조를 유지한다.
3. activation과 threshold unit은 완전 조합 또는 짧은 pipeline으로 구현한다.