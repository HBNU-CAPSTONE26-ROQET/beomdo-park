# 정책망 양자화 및 Export 명세

## 1. 목적

본 문서는 학습된 correction mask 예측망을 FPGA용 AI 가속기에 탑재하기 위한 양자화 형식과 weight export 절차를 정의한다.

## 2. 양자화 대상

| 대상 | 형식 |
|---|---|
| FC1 weight | INT8 |
| FC1 bias | INT16 |
| FC2 weight | INT8 |
| FC2 bias | INT16 |
| activation output | INT8 |
| output logits | INT16 |

## 3. 스케일 규칙

| 항목 | 규칙 |
|---|---|
| 입력 feature | 0 또는 1을 INT8로 표현 |
| weight scale | layer별 대칭 양자화 |
| bias scale | 누산 결과 스케일과 일치 |
| activation | ReLU 후 saturation 적용 |

## 4. Export 산출물

| 파일 | 설명 |
|---|---|
| weights_fc1_x.hex | X-path FC1 weight |
| bias_fc1_x.hex | X-path FC1 bias |
| weights_fc2_x.hex | X-path FC2 weight |
| bias_fc2_x.hex | X-path FC2 bias |
| weights_fc1_z.hex | Z-path FC1 weight |
| bias_fc1_z.hex | Z-path FC1 bias |
| weights_fc2_z.hex | Z-path FC2 weight |
| bias_fc2_z.hex | Z-path FC2 bias |
| model_manifest.json | dimension, scale, version, output bit 정보 |

## 5. 메모리 배치 규칙

| 메모리 영역 | 내용 |
|---|---|
| Bank 0 | X-path FC1 |
| Bank 1 | X-path FC2 (9 output logits) |
| Bank 2 | Z-path FC1 |
| Bank 3 | Z-path FC2 |
| Bias ROM | 각 layer bias |

## 6. 하드웨어 검증용 체크리스트

| 항목 | 확인 내용 |
|---|---|
| dimension match | RTL dimension과 export dimension 일치 |
| endian consistency | 파일 저장 순서 일치 |
| quantized inference parity | 소프트웨어 INT8 추론과 RTL mask 결과 일치 |
| version tagging | 모델 버전 추적 가능 여부 |