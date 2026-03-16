# Timing 및 Resource Budget 명세

## 1. 목적

본 문서는 정책망 추론 가속기의 cycle budget과 FPGA 자원 예산을 정의한다.

## 2. Cycle budget

| 단계 | 예상 cycle |
|---|---:|
| X-path FC1 | 24 |
| X-path FC2 | 20 |
| X-path overhead | 4 |
| Z-path FC1 | 24 |
| Z-path FC2 | 20 |
| Z-path overhead | 4 |
| Output write | 4 |
| 총합 | 100 |

100MHz 기준 100 cycle은 약 1.0μs에 해당한다.

## 3. 메모리 요구량

| 항목 | 개수 | 바이트 환산 |
|---|---:|---:|
| FC1 weights per path | 192 | 192B |
| FC2 weights per path | 160 | 160B |
| bias per path | 26 | 52B 내외 |
| 총 weight+bias 2개 path | - | 1KB 미만 |

## 4. 자원 예산 원칙

| 자원 | 원칙 |
|---|---|
| LUT | 제어 FSM, formatter, threshold unit 중심 |
| FF | 파이프라인 레지스터 및 상태 저장 |
| BRAM | weight memory 저장 우선 |
| DSP | PE array MAC 연산 우선 사용 |

## 5. 최적화 우선순위

1. 두 경로 순차 처리로 자원 절감.
2. weight memory bank 정렬로 주소 생성 단순화.
3. hidden size 확장보다 100MHz timing 확보를 우선.