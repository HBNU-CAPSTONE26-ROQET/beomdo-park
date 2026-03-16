# 박범도 모듈 명세

## 문서 정보

| 항목 | 내용 |
|---|---|
| 문서명 | 딥러닝 기반 QEC correction mask 예측망 설계 및 학습 명세 |
| 담당자 | 박범도 |
| 역할 구분 | 알고리즘 개발, 데이터 분석, 상위 시뮬레이션 및 테스트 환경 구축 |
| 문서 목적 | QEC용 correction mask 예측망 구조, 학습 방식, 데이터 생성, 양자화 및 export 기준을 규정 |

## 1. 역할 개요

박범도의 역할은 Surface Code 기반 QEC 문제를 correction mask 예측 문제로 재구성하고, FPGA에서 실행 가능한 소형 딥러닝 모델을 설계하는 것이다. 또한 학습 및 검증에 필요한 detector history 생성 환경과 ground-truth correction mask 생성 환경을 구축하며, 최종적으로 양자화된 weight와 bias를 하드웨어 구현팀에 전달한다.

| 세부 역할 | 설명 |
|---|---|
| 문제 정의 | QEC decoding을 correction mask 예측 문제로 정식화 |
| 상위 환경 구축 | syndrome generator 및 label generator 구축 |
| 모델 설계 | 2-layer mask prediction MLP 구조 정의 |
| 입력 정의 | 3-round detector history 및 feature representation 정의 |
| 학습 수행 | supervised multi-label 학습 수행 |
| 양자화 및 export | INT8 weight/activation 형식 정의 및 ROM 파일 생성 |

## 2. AI 모델 목적

본 모듈의 목적은 ambiguous detector pattern으로부터 correction mask를 직접 예측하는 모델을 설계하는 데 있다. 본 모델은 일반 목적 AI 모델이 아니라, QEC 디코딩이라는 특정 작업에 최적화된 소형 추론 모델이다.

## 3. 정책망 구조

### 3.1 경로 분리 구조

| 경로 | 입력 | 출력 |
|---|---|---|
| X-path | Z detector history 24-bit | X correction mask 9-bit |
| Z-path | X detector history 24-bit | Z correction mask 9-bit |

### 3.2 Layer 구성

| Layer | 입력 차원 | 출력 차원 | 연산 |
|---|---:|---:|---|
| FC1 | 24 | 16 | fully connected |
| ReLU | 16 | 16 | activation |
| FC2 | 16 | 9 | fully connected |
| Output | 9 | 9 | bitwise threshold |

### 3.3 수치 형식

| 항목 | 형식 |
|---|---|
| 입력 feature | INT8 |
| weight | INT8 |
| bias | INT16 |
| accumulator | INT16 |
| activation output | INT8 |
| output logits | INT16 또는 scaled INT8 |

## 4. 입력 및 정답 정의

| 항목 | 설명 |
|---|---|
| 입력 데이터 | 3-round detector history |
| 정답 | 9-bit correction mask |
| label 형식 | multi-hot bit vector |
| 추가 정보 | error type, ambiguity flag, sample id |

## 5. 학습 원칙

본 프로젝트는 딥러닝 기반 correction mask 예측망을 지향하며, 구현 안정성과 데이터 효율을 고려하여 baseline decoder로 생성된 mask를 supervised multi-label 방식으로 학습한다.

| 학습 단계 | 설명 |
|---|---|
| Step 1 | detector history와 mask label 기반 supervised training |
| Step 2 | threshold calibration |
| Step 3 | quantization-aware validation |
| Step 4 | FPGA export용 weight 고정 |

## 6. 산출물

| 산출물 | 설명 |
|---|---|
| network architecture spec | layer 크기, activation, mask bit 정의 |
| dataset package | 학습/검증/테스트 입력 데이터 |
| quantized weights | INT8 weight 및 bias |
| model evaluation report | exact match, bit accuracy, baseline 비교 |
| export package | ROM 초기화용 weight 파일 |

## 7. 박준성 및 장현석과의 인터페이스

### 7.1 박준성에게 전달

| 전달 항목 | 설명 |
|---|---|
| 입력 frame 구조 | 서버 입력 포맷 정의 |
| weight 파일 버전 | 실험 실행 시 사용할 모델 버전 |
| threshold 의미 | bitwise mask cutoff 해석 규칙 |

### 7.2 장현석에게 전달

| 전달 항목 | 설명 |
|---|---|
| layer dimension | FC1, FC2 크기 |
| quantized weight format | INT8 weight 및 INT16 bias 형식 |
| activation rule | ReLU 및 saturation 규칙 |
| output mapping | output bit와 data qubit 매핑 |

## 8. 세부 문서 안내

| 세부 문서 | 설명 |
|---|---|
| [specs/박범도/02_rl_problem_formulation_spec.md](specs/박범도/02_rl_problem_formulation_spec.md) | RL 문제 설정 및 reward 정의 |
| [specs/박범도/03_training_dataset_environment_spec.md](specs/박범도/03_training_dataset_environment_spec.md) | 학습/검증 데이터 및 상위 시뮬레이션 환경 |
| [specs/박범도/04_policy_export_quantization_spec.md](specs/박범도/04_policy_export_quantization_spec.md) | 양자화 및 weight export 규격 |

## 9. 제출용 요약 설명

박범도는 QEC 디코딩 문제를 correction mask 예측 문제로 정의하고, 해당 모델의 입력 표현, 학습 규칙, 양자화 형식, 하드웨어 전달 규격까지 책임진다. 따라서 박범도의 역할은 단순한 알고리즘 제안이 아니라, 실제 AI 가속기에서 실행될 모델 자체를 설계하고 제공하는 데 있다.