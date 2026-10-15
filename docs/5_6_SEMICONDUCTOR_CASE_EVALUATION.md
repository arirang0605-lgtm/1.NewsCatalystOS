# 5_6 — 반도체 관계 후보의 독립 사례 평가 기능

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

```sh
PYTHONPATH=src python3 scripts/evaluate_semiconductor_cases.py \
  --manifest /absolute/private/pins.json --labels /absolute/private/labels.json
```

현재 5_6 코드 경로의 합성 입력 시험만 완료. `precision_target_on_supplied_labels`는 제공된 라벨에서 산술 목표를 만족한다는 뜻이고 `independent_real_case_gate_verified=false`는 실제 독립 라벨·대표 표본·출시 인수가 별도라는 뜻이다. 5_2 공식 관계 실증과 실제 5_6 사례 평가는 자료가 생길 때 진행한다.
