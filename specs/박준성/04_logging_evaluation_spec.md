# Logging 및 Evaluation 명세

## 1. 목적

본 문서는 AI 가속기 실험 결과를 재현 가능하게 기록하고, 정확도 및 latency를 일관되게 평가하기 위한 로그 구조를 정의한다.

## 2. 로그 필드

| 필드명 | 설명 |
|---|---|
| run_id | 실험 식별자 |
| frame_id | 입력 frame 식별자 |
| model_version | 사용한 모델 버전 |
| corr_x_mask | X-path correction mask |
| corr_z_mask | Z-path correction mask |
| score_x | X-path confidence |
| score_z | Z-path confidence |
| latency_cycles | cycle 단위 지연 |
| exact_mask_match | 정답 mask 일치 여부 |
| bit_accuracy | bit 단위 일치율 |
| logical_success | 논리 성공 여부 |

## 3. 평가 지표

| 지표 | 설명 |
|---|---|
| exact match | correction mask 완전 일치율 |
| bit accuracy | correction mask bit 단위 정확도 |
| logical success rate | correction 성공률 |
| average latency | 평균 cycle |
| p95 latency | 상위 95% 지연 |
| threshold reject ratio | confidence 기준 제외 비율 |

## 4. 로그 산출물

| 파일 | 설명 |
|---|---|
| run_log.csv | 샘플 단위 실행 로그 |
| summary_report.csv | 평균 성능 요약 |
| failure_cases.csv | 오분류 및 timeout 사례 |

## 5. 재현성 규칙

1. 모든 로그는 model_version과 dataset_version을 함께 기록한다.
2. 동일 run_id에 대해 threshold와 mode를 고정 기록한다.
3. FPGA bitstream 버전도 별도 메타데이터로 남긴다.