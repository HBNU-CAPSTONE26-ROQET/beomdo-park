# 장현석 모듈 명세

## 문서 정보

| 항목 | 내용 |
|---|---|
| 문서명 | AI 가속기 RTL 구현 및 FPGA 검증 명세 |
| 담당자 | 장현석 |
| 역할 구분 | HDL 회로 설계 및 최적화 시뮬레이션 |
| 문서 목적 | QEC 정책망 추론용 AI 가속기의 RTL 구조, 실행 순서, 검증 기준을 규정 |

## 1. 역할 개요

장현석의 역할은 박범도가 설계한 correction mask 예측망을 실제 AI 추론 가속기 하드웨어로 구현하는 것이다. 본 역할은 MAC 기반 fully connected 연산, activation, threshold unit, weight memory, control FSM을 포함한 neural inference engine을 RTL 수준으로 설계하고 FPGA에서 검증하는 것을 포함한다.

| 세부 역할 | 설명 |
|---|---|
| AI engine 설계 | policy network inference datapath 구현 |
| 연산기 구현 | PE array, accumulation, activation, threshold unit 구현 |
| 메모리 구조 설계 | weight memory, feature buffer, score buffer 구성 |
| 제어 로직 설계 | layer execution FSM 및 상태 관리 |
| FPGA 검증 | timing, resource, latency 검증 |

## 2. 가속기 목적

본 모듈의 목적은 강화학습 정책망의 추론을 일반 CPU가 아닌 전용 하드웨어 데이터패스로 수행하는 것이다. 즉, 본 모듈은 AI 가속기의 핵심 정의에 해당하는 AI 모델 특정 연산에 최적화된 특수 하드웨어를 구현하는 역할을 가진다.

## 3. 정책망 실행 대상

| 항목 | 값 |
|---|---|
| 입력 차원 | 24 |
| Hidden 차원 | 16 |
| 출력 비트 수 | 9 |
| 모델 수 | X-path, Z-path 2개 |
| 수치 형식 | INT8 / INT16 fixed-point |

## 4. Top-level 가속기 구조

| 순서 | 모듈명 | 역할 |
|---|---|---|
| 1 | syndrome_buffer | 3-round history 저장 |
| 2 | feature_formatter | 입력 binary history를 INT8 feature로 정규화 |
| 3 | weight_memory | layer별 weight/bias 저장 |
| 4 | pe_array | 병렬 MAC 연산 수행 |
| 5 | accumulation_unit | partial sum 누적 |
| 6 | activation_unit | ReLU 수행 |
| 7 | score_buffer | hidden vector 및 logits 저장 |
| 8 | threshold_unit | 최종 correction mask bit 결정 |
| 9 | confidence_unit | confidence score 산출 |
| 10 | output_formatter | correction mask 정렬 및 출력 |
| 11 | control_fsm | layer 실행 및 channel 전환 제어 |

## 5. 구현 방식

### 5.1 연산 원리

가속기는 fully connected layer의 행렬-벡터 곱을 fixed-point MAC 연산으로 수행한다.

| Layer | MAC 수 |
|---|---:|
| FC1 | 12 x 16 = 192 |
| FC2 | 16 x 9 = 144 |

하나의 경로당 총 352 MAC이 필요하며, X-path와 Z-path를 동일 엔진으로 순차 처리하거나 자원이 허용되면 병렬 처리할 수 있다.

### 5.2 권장 PE Array

| 항목 | 권장값 |
|---|---|
| PE 수 | 8 |
| PE 연산 | INT8 x INT8 -> INT16 accumulate |
| FC1 예상 cycle | 192 / 8 = 24 cycle |
| FC2 예상 cycle | 144 / 8 = 18 cycle |
| 경로당 추론 cycle | 제어 오버헤드 포함 약 46 cycle |

100MHz 기준 두 경로 순차 처리 시 약 1μs 이내 동작을 목표로 한다.

## 6. 검증 및 최적화 목표

| 항목 | 목표 |
|---|---|
| 기능 일치 | 소프트웨어 policy inference와 동일 결과 출력 |
| latency | 두 경로 합산 1μs 내외 |
| 자원 사용 | FPGA 실습 보드에서 수용 가능한 LUT/FF/BRAM 사용량 |
| 확장성 | hidden size 변경 가능 구조 유지 |

## 7. 박범도 및 박준성과의 연계

### 7.1 박범도와의 연계

| 항목 | 설명 |
|---|---|
| layer dimension | 정책망 구조 고정 |
| weight quantization | INT8/INT16 형식 일치 |
| activation rule | ReLU 및 saturation 규칙 통일 |
| output mapping | output bit와 correction qubit mapping 일치 |

### 7.2 박준성과의 연계

| 항목 | 설명 |
|---|---|
| input packet format | x_hist, z_hist 패킹 형식 일치 |
| control register | start, mode, threshold, version select 규약 |
| result format | correction mask, score, latency readback 형식 일치 |

## 8. 세부 문서 안내

| 세부 문서 | 설명 |
|---|---|
| [specs/장현석/02_rtl_architecture_spec.md](specs/장현석/02_rtl_architecture_spec.md) | AI 가속기 RTL 상세 구조 |
| [specs/장현석/03_verification_plan_spec.md](specs/장현석/03_verification_plan_spec.md) | 기능/합성/FPGA 검증 계획 |
| [specs/장현석/04_timing_resource_budget_spec.md](specs/장현석/04_timing_resource_budget_spec.md) | latency 및 자원 예산 |

## 9. 제출용 요약 설명

장현석은 correction mask 예측망의 fully connected 추론 연산을 전용 RTL 데이터패스로 구현하고, 이를 FPGA에서 검증하는 역할을 담당한다. 따라서 장현석의 역할은 단순 decoder 회로 구현이 아니라, 실제 AI 추론 연산을 가속하는 특수 하드웨어 블록을 설계하는 데 있다.