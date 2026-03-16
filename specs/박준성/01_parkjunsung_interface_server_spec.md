# 박준성 모듈 명세

## 문서 정보

| 항목 | 내용 |
|---|---|
| 문서명 | AI 가속기 통합 인터페이스 및 제어 서버 명세 |
| 담당자 | 박준성 |
| 역할 구분 | 통합 인터페이스 및 서버 구축 |
| 문서 목적 | AI 가속기 SoC의 입력 패킷, weight loading, 제어 레지스터, 실행 및 결과 수집 구조를 규정 |

## 1. 역할 개요

박준성의 역할은 박범도가 설계한 정책망과 장현석이 구현한 AI 가속기 RTL을 하나의 실행 가능한 시스템으로 연결하는 것이다. 이를 위해 입력 frame 전송 구조, weight/bias 로딩 절차, 제어 레지스터 맵, 실행 순서, 결과 수집 및 로그화를 담당한다.

| 세부 역할 | 설명 |
|---|---|
| 입력 패킷 구성 | detector history를 accelerator 입력 형식으로 패킹 |
| 제어 경로 설계 | start, mode, threshold, channel select 제어 |
| 모델 로딩 지원 | weight/bias 파일 배치 및 버전 관리 |
| 결과 수집 | correction mask, confidence, latency 로그화 |
| 실험 orchestration | 반복 실행 및 비교 실험 자동화 |

## 2. 시스템 목적

본 모듈의 목적은 AI 가속기 SoC가 단순 회로 수준이 아니라 실제 실행 가능한 추론 시스템으로 동작하도록 만드는 것이다. 즉, 박준성의 시스템 계층은 모델, 입력 데이터, 제어 신호, 결과 로그를 하나의 일관된 흐름으로 연결한다.

## 3. 상위 구성 요소

| 구성 요소 | 역할 |
|---|---|
| Frame Packer | detector history 패킹 |
| Weight Loader | 모델 weight/bias 로딩 |
| Control Server | accelerator 제어 및 상태 확인 |
| Result Reader | correction mask/confidence/latency 수집 |
| Log Manager | 로그 저장 및 평가용 CSV 생성 |

## 4. 입출력 인터페이스 개요

### 4.1 입력 패킷

| 필드명 | 비트 폭 | 설명 |
|---|---:|---|
| frame_id | 32 | frame 식별자 |
| x_hist | 24 | X-path 입력 history |
| z_hist | 24 | Z-path 입력 history |
| decoder_mode | 2 | inference mode |
| confidence_threshold | 8 | reject threshold |

### 4.2 출력 패킷

| 필드명 | 비트 폭 | 설명 |
|---|---:|---|
| frame_id | 32 | 입력 frame 식별자 |
| corr_x_mask | 9 | X-path correction mask |
| corr_z_mask | 9 | Z-path correction mask |
| score_x | 16 | X-path confidence |
| score_z | 16 | Z-path confidence |
| latency_cycles | 16 | 추론 cycle 수 |

## 5. 제어 기능

| 제어 항목 | 설명 |
|---|---|
| accelerator_enable | 가속기 활성화 |
| start_inference | 추론 시작 |
| model_version_select | 사용할 weight set 선택 |
| threshold_set | confidence threshold 설정 |
| status_read | busy/done/error 상태 조회 |

## 6. 박범도 및 장현석과의 인터페이스

### 6.1 박범도와의 연계

| 항목 | 설명 |
|---|---|
| dataset version | 입력 데이터셋 버전 일치 |
| model package version | weight export 버전 일치 |
| threshold meaning | confidence 기준 해석 일치 |

### 6.2 장현석과의 연계

| 항목 | 설명 |
|---|---|
| register map | 제어 레지스터 정의 |
| memory loading protocol | weight memory write 규약 |
| ready/busy/done semantics | 상태 플래그 해석 일치 |
| output readback format | 결과 데이터 형식 통일 |

## 7. 세부 문서 안내

| 세부 문서 | 설명 |
|---|---|
| [specs/박준성/02_frame_interface_spec.md](specs/박준성/02_frame_interface_spec.md) | 입력 frame 및 패킷 규격 |
| [specs/박준성/03_control_server_architecture_spec.md](specs/박준성/03_control_server_architecture_spec.md) | 제어 서버 및 register map 구조 |
| [specs/박준성/04_logging_evaluation_spec.md](specs/박준성/04_logging_evaluation_spec.md) | 실행 로그 및 평가 데이터 구조 |

## 8. 제출용 요약 설명

박준성은 박범도가 설계한 정책망과 장현석이 구현한 AI 가속기를 하나의 실행 가능한 시스템으로 연결하는 역할을 담당한다. 따라서 박준성의 역할은 입력 데이터 전달에 그치지 않고, 모델 로딩, 제어 신호 구성, 실행 흐름 관리, 결과 수집까지 포함하는 시스템 integration에 있다.