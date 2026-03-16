# AI 가속기 검증 계획 명세

## 1. 목적

본 문서는 RTL, 합성, FPGA 단계별 검증 항목을 정의한다.

## 2. 기능 검증

| 항목 | 설명 |
|---|---|
| golden parity | 소프트웨어 INT8 추론 결과와 일치 여부 |
| mask mapping | output bit와 correction mask 해석 일치 |
| threshold behavior | confidence threshold 동작 확인 |
| mode control | normal, debug, single-path 모드 확인 |

## 3. 테스트 벡터 구성

| 벡터 유형 | 설명 |
|---|---|
| nominal cases | 일반 syndrome 샘플 |
| ambiguous cases | 애매한 패턴 집중 샘플 |
| no-op cases | correction 불필요 샘플 |
| invalid cases | 잘못된 입력 또는 timeout 유도 샘플 |

## 4. 합성 검증

| 항목 | 설명 |
|---|---|
| timing slack | 목표 클럭 충족 여부 |
| LUT/FF/BRAM | 자원 사용량 측정 |
| critical path | 병목 경로 식별 |

## 5. FPGA 검증

| 항목 | 설명 |
|---|---|
| register access | 제어 서버와 레지스터 연동 |
| real run latency | 실측 cycle 및 시간 |
| repeated stability | 반복 실행 안정성 |
| output logging | 로그 수집 일관성 |

## 6. 통과 기준

| 항목 | 기준 |
|---|---|
| 기능 일치율 | 테스트 벡터 기준 100% |
| 클럭 | 100MHz 달성 |
| end-to-end 추론 | 두 경로 1μs 내외 |