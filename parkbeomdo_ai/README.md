# Park Beom-do AI Pipeline

이 디렉터리는 박범도 담당 범위인 QEC correction mask network 데이터 생성, 학습, 평가, FPGA export 코드를 담는다.

## 구성

- `config.py`: 모델, 데이터셋, 학습, export 기본 설정
- `dataset.py`: 3-round detector history dataset 생성 (Stim + PyMatching)
- `model.py`: 24-16-9 MLP correction mask 예측망 정의
- `train.py`: 데이터셋 생성 + X/Z path 학습 + 양자화 검증 통합 파이프라인
- `export.py`: 학습된 모델을 INT8/INT16 hex 파일로 FPGA export
- `analyze_dem_mapping.py`: DEM term → circuit fault 매핑 분석
- `analyze_solution_edge_support.py`: decoder solution edge → data-qubit support 분석

## 실행 예시

```bash
pip install -r requirements.txt

# 기본 학습 (20000 샘플, 50 epoch, cosine annealing, early stopping, QAT 검증 포함)
python -m parkbeomdo_ai.train

# 커스텀 파라미터
python -m parkbeomdo_ai.train --samples 50000 --epochs 80 --hidden-dim 32

# 외부 데이터셋에서 학습 (train_from_dataset 기능 통합)
python -m parkbeomdo_ai.train --dataset artifacts/data/support_qec_dataset.npz --prefix support

# FPGA weight export
python -m parkbeomdo_ai.export
```

## 주요 산출물

- `artifacts/data/synthetic_qec_dataset.npz` — 학습 데이터셋
- `artifacts/models/policy_{x,z}.pt` — 학습된 모델
- `artifacts/reports/run_summary.json` — 학습 결과 (양자화 검증 포함)
- `artifacts/export/*.hex` — FPGA ROM 초기화용 weight 파일
- `artifacts/export/model_manifest.json` — 모델 차원/스케일 정보