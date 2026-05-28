# Grid Guardian — система предиктивного обслуживания

Прототип (PoC) предиктивного обслуживания трансформаторов 35 кВ+ для ВКР магистратуры «Управление IT-продуктами и проектами». Объект — ПАО «Россети».

Назначение — доказать на синтетических, но физически реалистичных данных, что обслуживание «по прогнозу ML-модели» эффективнее обслуживания «по календарю» и «по факту аварии», и просчитать экономику.

**Демо:** https://lodgerpro.github.io/grid-guardian-pdm/ (QR — `artifacts/qr_demo.png`).

## Архитектура

Две части:

- **Python-ядро** (`src/`) — считает всё заранее: генерация данных → feature engineering → обучение модели → экономика → выгрузка JSON.
- **Веб-витрина** (`app/`) — статичный React+Vite-фронт, читает готовые JSON из `app/public/data/*.json`. Никакого Python во время показа.

Принцип: сначала полностью отлажено ядро (Этапы 1–5), потом строится витрина (Этап 6) поверх проверенных данных.

## Запуск ядра — пайплайн с нуля

```bash
pip install -r requirements.txt

python src/generate_data.py        # Этап 1: 50 ед × 2 года × 18 параметров → data/telemetry.parquet
python src/feature_engineering.py  # Этап 2: 95 признаков → data/features.parquet
python src/build_target.py         # Этап 3: 3-классовая метка, горизонт 72 ч → data/labels.parquet
python src/train_model.py          # Этап 4: XGBoost, 2 сплита → artifacts/model.json, metrics.json, 3 PNG
python src/horizon_sensitivity.py  # Этап 4+: sweep {24, 72, 168} ч → horizon_sensitivity.json + PNG
python src/economics.py            # Этап 5: NPV/IRR/PP/DPP/ROI + 3×3 sensitivity + масштабирование
python src/export_for_frontend.py  # Этап 6: компактные JSON для витрины → app/public/data/*.json
python src/make_qr.py              # QR-код демо-ссылки → artifacts/qr_demo.png
```

Random seed=42 — все цифры воспроизводимы.

## Запуск витрины (локально)

```bash
cd app
npm install
npm run dev
# Открыть http://localhost:5173/
```

Для production-сборки:

```bash
npm run build      # → app/dist/
npm run preview    # локально просмотреть production-сборку
```

## Деплой на GitHub Pages

В репозитории настроен workflow `.github/workflows/deploy.yml`:

1. В **Settings → Pages** выбрать **Source: GitHub Actions**.
2. Любой push в `main` (затрагивающий `app/`) триггерит деплой автоматически.
3. URL — `https://<user>.github.io/<repo>/`. После первого деплоя обновить `DEFAULT_URL` в `src/make_qr.py` и перезапустить `make_qr.py`.

## Структура артефактов

```
artifacts/
  data_summary.json         # Этап 1+3: объём данных, распределение классов, расписание деградации
  feature_list.json         # Этап 2+3: 95 признаков по 6 группам + список исключений из обучения
  metrics.json              # Этап 4: метрики обоих сплитов + no-ML baseline
  model.json                # Этап 4: XGBoost native (хронологический сплит, primary)
  confusion_matrix.png      # Этап 4: confusion matrix (counts + row-normalized)
  roc_curve.png             # Этап 4: ROC OvR per-class
  feature_importance.png    # Этап 4: top-15 признаков по gain
  horizon_sensitivity.json  # Этап 4: метрики при {24, 72, 168} ч
  horizon_sensitivity.png   # Этап 4: recall_High + F1_High по горизонту, ML vs baseline
  economics.json            # Этап 5: NPV/IRR/PP/DPP/ROI + 3×3 sensitivity + масштабирование, со ссылками на references/
  cashflow.png              # Этап 5: 5-летний денежный поток базового сценария
  sensitivity.png           # Этап 5: heatmap NPV (ставка × снижение аварийности)
  scaling.png               # Этап 5: годовая экономия и NPV при масштабировании на 35 кВ+
  qr_demo.png               # QR-код на опубликованную витрину
```

## Технологический стек

**Ядро:** Python 3.11+, numpy, pandas, pyarrow, scikit-learn, xgboost, matplotlib, qrcode, pypdf.

**Витрина:** React 18 + Vite 5 + TypeScript, react-router-dom, recharts, react-leaflet, Leaflet (CartoDB Dark Matter тайлы).

**Дизайн-система:** холодный тёмно-синий (`oklch(0.16 0.025 250)`), циан-акцент (`oklch(0.78 0.14 205)`), светофор зелёный/янтарный/красный одной хромы. Шрифты: Space Grotesk (заголовки) + Inter (UI) + JetBrains Mono (числа и ID). Полная дизайн-система зафиксирована в `app/src/styles/shared.css` (передана из Claude Design).

**Импортонезависимость:** только open-source библиотеки, без проприетарных облачных сервисов.

## Разделы витрины

1. **Главная** — KPI парка, кольцевая диаграмма распределения рисков, активные предупреждения, карточка модели.
2. **Прогноз риска** *(приоритет для защиты)* — ранжированный список 50 единиц, разложение по факторам, чувствительность к горизонту.
3. **Финансы** *(приоритет для защиты)* — KPI, ползунки параметров, heatmap NPV 3×3, денежный поток, масштабирование.
4. **Карта** — Leaflet с реальными координатами 10 подстанций (Мурманск ↔ Красноярск), маршрут бригады запад→восток.
5. **Мониторинг** — сравнение «здоровый vs деградирующий» юнит на 3 параметрах × 30 дней.

Все разделы адаптивны под мобильные (≤ 760 px): сайдбар скрывается, появляется нижняя таб-бар, KPI в 2 колонки.

## Лицензия

MIT.
