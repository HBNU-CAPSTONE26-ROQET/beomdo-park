# Control Server 아키텍처 명세

## 1. 목적

본 문서는 AI 가속기 실험 실행을 위한 제어 서버 구조와 레지스터 맵을 정의한다.

## 2. 서버 구성

| 구성 요소 | 역할 |
|---|---|
| Session Manager | 실험 세션 관리 |
| Model Loader | weight set 버전 선택 |
| Register Controller | 레지스터 read/write |
| Job Executor | frame submit 및 완료 대기 |
| Result Store | 결과 저장 |

## 3. 권장 레지스터 맵

| 주소 | 이름 | 설명 |
|---|---|---|
| 0x00 | CTRL | enable, start, reset |
| 0x04 | STATUS | ready, busy, done, error |
| 0x08 | MODE | decoder mode |
| 0x0C | THRESH | confidence threshold |
| 0x10 | MODEL_VER | weight set version |
| 0x20 | FRAME_ID | 입력 frame id |
| 0x24 | X_HIST_LO | x_hist[15:0] |
| 0x28 | X_HIST_HI | x_hist[23:16] |
| 0x2C | Z_HIST_LO | z_hist[15:0] |
| 0x30 | Z_HIST_HI | z_hist[23:16] |
| 0x40 | CORR_X | 결과 corr_x_mask |
| 0x44 | CORR_Z | 결과 corr_z_mask |
| 0x48 | SCORE_X | 결과 score_x |
| 0x4C | SCORE_Z | 결과 score_z |
| 0x50 | LATENCY | latency counter |

## 4. 실행 시퀀스

1. MODEL_VER, MODE, THRESH를 설정한다.
2. FRAME_ID, X_HIST, Z_HIST를 기록한다.
3. CTRL.start를 1로 설정한다.
4. STATUS.done이 1이 될 때까지 polling 또는 interrupt 대기한다.
5. 결과 레지스터를 읽고 로그에 저장한다.

## 5. API 예시

| API | 설명 |
|---|---|
| load_model(version) | 모델 버전 선택 |
| submit_frame(frame) | frame 전송 |
| run_once() | 1회 추론 실행 |
| read_result(frame_id) | 결과 조회 |
| dump_status() | 상태 정보 출력 |