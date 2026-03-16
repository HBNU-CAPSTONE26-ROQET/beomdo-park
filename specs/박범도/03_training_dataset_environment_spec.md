# 학습 데이터셋 및 상위 시뮬레이션 환경 명세

## 1. 목적

본 문서는 정책망 학습과 하드웨어 검증에 공통으로 사용할 syndrome history 데이터셋 및 상위 시뮬레이션 환경의 구성 기준을 정의한다.

## 2. 환경 구성

| 구성 요소 | 기능 |
|---|---|
| Error Injector | physical error 삽입 |
| Detector Simulator | round별 detector event 생성 |
| Label Generator | 정답 correction mask 생성 |
| Dataset Splitter | train, validation, test 분리 |
| Exporter | CSV 또는 binary dataset 출력 |

## 3. 샘플 단위 정의

| 필드명 | 설명 |
|---|---|
| sample_id | 샘플 식별자 |
| x_r0, x_r1, x_r2 | X detector history rounds |
| z_r0, z_r1, z_r2 | Z detector history rounds |
| mask_x | X-path 9-bit correction mask 정답 |
| mask_z | Z-path 9-bit correction mask 정답 |
| error_type | injected error 유형 |
| ambiguity_flag | ambiguous sample 여부 |

## 4. 데이터셋 분할 기준

| 구분 | 비율 | 목적 |
|---|---:|---|
| Train | 70% | 가중치 학습 |
| Validation | 15% | threshold 및 epoch 선택 |
| Test | 15% | 최종 보고 성능 측정 |

## 5. 생성 원칙

1. 학습과 FPGA 검증에 동일한 output bit mapping을 사용한다.
2. X-path와 Z-path label은 각각 독립 저장한다.
3. ambiguous pattern 비중을 별도 태깅하여 분석 가능하게 한다.
4. 동일 sample_id는 재현 가능한 랜덤 시드로 복원 가능해야 한다.

## 6. 출력 파일 형식

| 형식 | 설명 |
|---|---|
| CSV | 실험 추적 및 분석용 |
| NPY 또는 binary | 학습 로더 및 FPGA 테스트 입력 생성용 |
| Manifest | 버전, 샘플 수, split 정보 기록 |

## 7. 검증 항목

| 항목 | 설명 |
|---|---|
| label consistency | 동일 syndrome에 대한 label 일관성 |
| split integrity | train/validation/test 중복 방지 |
| ambiguity coverage | 애매한 패턴 포함 여부 |
| hardware replayability | FPGA 테스트 벡터로 재사용 가능 여부 |