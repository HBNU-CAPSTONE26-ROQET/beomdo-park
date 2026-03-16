# QEC Correction Mask 예측 문제 정식화 명세

## 1. 목적

본 문서는 Surface Code distance-3 디코딩 문제를 correction mask 예측 문제로 정식화하는 기준을 정의한다. 목표는 하드웨어 구현이 가능한 작은 mask prediction 구조를 유지하면서도 ambiguous detector pattern에 대한 복원 성능을 확보하는 것이다.

## 2. 에이전트 관점 정의

| 항목 | 정의 |
|---|---|
| 환경 | Surface Code d=3 detector history generator |
| 상태 | 3-round detector history 24-bit |
| 출력 | 9-bit correction mask |
| 모델 | 2-layer MLP 기반 mask prediction network |
| 학습 목표 | baseline decoder mask 복원 |

## 3. 상태 정의

| 경로 | 상태 정의 | 비트 폭 |
|---|---|---:|
| X-path | z detector history = 3 x 8 bits | 24 |
| Z-path | x detector history = 3 x 8 bits | 24 |

입력은 detector event의 binary history이며, feature formatter에서 각 bit를 0 또는 1의 INT8 feature로 변환한다.

## 4. 출력 정의

| Mask Bit | 의미 |
|---|---|
| bit0 | q0 correction |
| bit1 | q1 correction |
| bit2 | q2 correction |
| bit3 | q3 correction |
| bit4 | q4 correction |
| bit5 | q5 correction |
| bit6 | q6 correction |
| bit7 | q7 correction |
| bit8 | q8 correction |

출력은 9개 data qubit에 대한 correction 여부를 직접 나타내는 multi-label mask로 정의한다.

## 5. 학습 손실 정의

| 항목 | 정의 |
|---|---:|
| 기본 손실 | BCEWithLogitsLoss |
| bit 불일치 패널티 | bitwise mismatch 최소화 |
| exact match 목표 | 전체 9-bit mask 일치 최대화 |

## 6. 정책망 구조 고정값

| 항목 | 값 |
|---|---|
| 입력 차원 | 24 |
| 은닉 차원 | 16 |
| 출력 차원 | 9 |
| activation | ReLU |
| 추론 형식 | INT8 fixed-point |

## 7. 학습 전략

| 단계 | 설명 |
|---|---|
| Supervised training | baseline decoder mask 기반 학습 |
| Threshold calibration | bitwise threshold 산정 |
| Export lock | 하드웨어 배포용 가중치 고정 |

## 8. 성능 평가 기준

| 지표 | 설명 |
|---|---|
| exact match | 전체 9-bit mask 정답률 |
| bit accuracy | bit 단위 정답률 |
| logical success rate | correction 후 논리 성공률 |
| Hamming distance | 예측 mask와 정답 mask 차이 |

## 9. 하드웨어 전달 항목

| 전달 항목 | 설명 |
|---|---|
| layer dimension | 24-16-9 고정 |
| output bit mapping | output bit와 data qubit index 매핑 |
| threshold | bitwise cutoff |
| quantized parameters | INT8 weight, INT16 bias |