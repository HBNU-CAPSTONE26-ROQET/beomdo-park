# QEC AI 가속기 SoC 프로젝트 통합 명세

## 문서 정보

| 항목 | 내용 |
|---|---|
| 문서명 | QEC AI 가속기 SoC 프로젝트 통합 명세 |
| 작성일 | 2026-03-09 |
| 문서 목적 | 프로젝트의 연구 목표, AI 가속기 정의, 시스템 아키텍처, 팀원별 역할 및 문서 구조를 통합적으로 설명 |
| 적용 범위 | Surface Code 기반 correction mask 예측용 온디바이스 AI 가속기 SoC |

## 1. 프로젝트 정의

본 프로젝트는 양자 오류 정정 문제를 해결하기 위한 온디바이스 AI 가속기 SoC를 설계하는 것을 목적으로 한다. 본 문서에서 AI 가속기란 단순히 AI를 사용하는 시스템 전체를 의미하지 않고, 강화학습 기반 정책망의 추론 연산을 빠르게 수행하도록 최적화된 전용 하드웨어 블록을 의미한다.

즉, 본 프로젝트의 중심은 다음과 같다.

1. Surface Code의 detector history를 입력으로 사용하는 correction mask 예측망을 설계한다.
2. 해당 정책망의 추론을 fixed-point MAC 연산과 bitwise threshold 출력에 최적화된 전용 하드웨어로 구현한다.
3. 이 AI 추론 블록을 syndrome buffer, 제어 로직, 인터페이스와 결합하여 하나의 SoC 구조로 통합한다.

## 2. 왜 AI 가속기인가

양자 오류 정정 시스템에서 classical decoder는 반복 측정된 syndrome을 빠르게 해석해야 한다. 일반적인 CPU 또는 외부 서버 기반 처리 방식은 전송 지연과 소프트웨어 처리 지연이 누적될 수 있으며, 이는 실시간 오류 정정의 병목으로 작용한다.

본 프로젝트는 이러한 문제를 해결하기 위하여 correction mask 예측망의 추론 연산 자체를 하드웨어로 옮긴다. 따라서 본 연구는 단순히 AI 모델을 사용하는 것이 아니라, AI 모델의 핵심 계산을 전용 데이터패스로 가속하는 AI accelerator 설계 과제에 해당한다.

## 3. AI 모델 정의

본 프로젝트의 AI 모델은 Surface Code distance-3용 채널 분리형 correction mask 예측망이다. X-path와 Z-path는 동일한 구조를 사용하되, 각기 다른 detector history와 가중치를 사용한다.

| 항목 | 정의 |
|---|---|
| 입력 | 3-round detector history 24-bit per path |
| 모델 구조 | 2-layer mask prediction MLP |
| Layer 1 | 24 x 16 fully connected |
| Activation | ReLU |
| Layer 2 | 16 x 9 fully connected |
| 출력 | 9-bit correction mask logits |
| 최종 연산 | bitwise threshold 및 confidence 산출 |
| 수치 형식 | INT8 weight, INT8 activation, INT16 accumulator |

본 모델은 대규모 범용 AI 모델이 아니라, QEC 디코딩이라는 특정 작업에 최적화된 소형 정책망이며, FPGA 상에서 실제 구현 가능한 수준으로 설계한다.

## 4. 시스템 구성 개요

전체 시스템은 상위 시뮬레이션 및 테스트 환경, 통합 인터페이스 및 제어 서버, AI 가속기 SoC, 결과 수집 및 분석 계층으로 구성된다.

| 단계 | 구성 요소 | 주요 기능 |
|---|---|---|
| 1 | 상위 시뮬레이션 및 테스트 환경 | detector history 및 ground-truth correction mask 생성 |
| 2 | 통합 인터페이스 및 제어 서버 | 입력 frame 구성, 모델 설정, FPGA 제어, 결과 수집 |
| 3 | AI 가속기 SoC | syndrome buffer, neural inference engine, control FSM, output formatter 수행 |
| 4 | 결과 분석 계층 | 정확도, latency, resource utilization 분석 |

### 4.1 AI 가속기 SoC 내부 블록

| 블록 | 기능 |
|---|---|
| Syndrome Buffer | 3-round syndrome history 저장 |
| Feature Formatter | binary syndrome을 INT8 feature vector로 변환 |
| Weight Memory | 정책망 가중치 및 bias 저장 |
| PE Array | fully connected layer MAC 연산 수행 |
| Activation Unit | ReLU 수행 |
| Score Buffer | intermediate feature 및 logits 저장 |
| Threshold / Confidence Unit | bitwise correction mask 및 confidence 계산 |
| Control FSM | layer 실행 순서 제어 |
| Output Formatter | correction mask와 상태 출력 생성 |
| AXI-Lite / AXI-Stream Interface | 제어 및 데이터 송수신 |

## 5. 팀원별 역할 체계

| 팀원 | 담당 영역 | 핵심 책임 | 주요 산출물 |
|---|---|---|---|
| 박범도 | 알고리즘, correction mask 예측망, 상위 시뮬레이션 및 테스트 환경 | QEC 문제 정의, mask prediction 구조 설계, 학습 데이터셋 생성, 학습 및 양자화, weight export | mask network spec, dataset, quantized weights, accuracy report |
| 박준성 | 통합 인터페이스 및 제어 서버 | frame 패킹, 레지스터 제어, weight loading, 실행 orchestration, 결과 수집 및 로그화 | control server, register map, execution log, evaluation CSV |
| 장현석 | AI 가속기 RTL 및 FPGA 검증 | neural inference engine 구현, PE array 설계, memory mapping, timing/resource 최적화, FPGA 검증 | Verilog RTL, testbench, synthesis report, FPGA bitstream |

## 6. 모듈 간 연계 구조

| 제공자 | 수신자 | 전달 내용 |
|---|---|---|
| 박범도 | 박준성 | syndrome dataset 구조, model weight 파일 형식, threshold 의미 |
| 박범도 | 장현석 | network dimension, quantized weight format, activation format, layer execution 규칙 |
| 박준성 | 장현석 | register map, frame input 규격, 실행 시퀀스, 결과 readback 규격 |
| 장현석 | 박준성 | accelerator ready/busy/done 규약, weight memory load 방법, latency counter 위치 |
| 장현석 | 박범도 | quantization 적용 후 모델 손실, MAC precision 제약, memory budget |

## 7. 구현 목표

| 항목 | 목표 |
|---|---|
| 추론 대상 | X-path, Z-path correction mask 추론 |
| 입력 형식 | 24-bit detector history per path |
| 출력 형식 | 9-bit correction mask, confidence |
| 하드웨어 유형 | fixed-point MLP inference accelerator |
| 구현 플랫폼 | FPGA 기반 RTL prototype |
| 성능 목표 | 100MHz 기준 두 경로 추론을 1μs 내외로 수행 |

## 8. 문서 구조

| 구분 | 상위 문서 | 세부 문서 |
|---|---|---|
| 프로젝트 전체 | [specs/00_project_overview_spec.md](specs/00_project_overview_spec.md) | 본 문서가 최상위 문서 |
| 박범도 | [specs/박범도/01_parkbeomdo_algorithm_rl_spec.md](specs/박범도/01_parkbeomdo_algorithm_rl_spec.md) | [specs/박범도/02_rl_problem_formulation_spec.md](specs/박범도/02_rl_problem_formulation_spec.md), [specs/박범도/03_training_dataset_environment_spec.md](specs/박범도/03_training_dataset_environment_spec.md), [specs/박범도/04_policy_export_quantization_spec.md](specs/박범도/04_policy_export_quantization_spec.md) |
| 박준성 | [specs/박준성/01_parkjunsung_interface_server_spec.md](specs/박준성/01_parkjunsung_interface_server_spec.md) | [specs/박준성/02_frame_interface_spec.md](specs/박준성/02_frame_interface_spec.md), [specs/박준성/03_control_server_architecture_spec.md](specs/박준성/03_control_server_architecture_spec.md), [specs/박준성/04_logging_evaluation_spec.md](specs/박준성/04_logging_evaluation_spec.md) |
| 장현석 | [specs/장현석/01_janghyeonseok_rtl_fpga_spec.md](specs/장현석/01_janghyeonseok_rtl_fpga_spec.md) | [specs/장현석/02_rtl_architecture_spec.md](specs/장현석/02_rtl_architecture_spec.md), [specs/장현석/03_verification_plan_spec.md](specs/장현석/03_verification_plan_spec.md), [specs/장현석/04_timing_resource_budget_spec.md](specs/장현석/04_timing_resource_budget_spec.md) |

## 9. 제출용 요약 설명

본 프로젝트는 QEC 문제에 AI를 적용하는 수준을 넘어, correction mask 예측망의 추론을 전용 하드웨어로 가속하는 AI accelerator SoC 설계 과제이다. 박범도는 정책망과 학습 환경을 설계하고, 박준성은 이를 실제 시스템으로 구동하기 위한 제어 및 데이터 경로를 구성하며, 장현석은 mask 추론 엔진을 RTL과 FPGA로 구현한다. 따라서 본 프로젝트는 AI 모델, 시스템 소프트웨어, 전용 하드웨어를 하나의 구조로 통합하는 공동 설계 프로젝트로 이해되어야 한다.