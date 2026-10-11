# 非机动车违规智能检测

The application now contains a real upload-to-inference pipeline:

1. Vue uploads an image or video to FastAPI.
2. A custom Ultralytics YOLO model detects helmets and bare heads while a COCO YOLO11s model detects people and two-wheelers.
3. The rule engine associates riders with vehicles and head detections with riders.
4. Video events require repeated detections on the same ByteTrack trajectory.
5. Results are returned as annotated evidence and remain pending until human review.

## First-time setup

```powershell
cd E:\基于YOLO\backend
.\setup.ps1
```

Place the trained custom checkpoint at:

```text
E:\基于YOLO\backend\models\best.pt
```

Start the backend:

```powershell
cd E:\基于YOLO\backend
.\run.ps1
```

Start the frontend in another terminal:

```powershell
cd E:\基于YOLO\frontend
npm run dev
```

The API status endpoint is `http://127.0.0.1:8000/api/health`.

Helmet/head and person/vehicle inference use separate confidence thresholds.
The defaults are `0.20` and `0.20` respectively because small or occluded
two-wheelers commonly score lower than people. Override them with
`YOLO_HELMET_CONFIDENCE` and `YOLO_CONTEXT_CONFIDENCE` when calibrating on a
new validation set. For image uploads, vehicles whose rider has an unknown
helmet state trigger a second pass over the rider's head crop at `0.08`; set
`YOLO_ROI_HELMET_CONFIDENCE` to calibrate that gated fallback.

## Model training

Prepare a YOLO-format custom dataset with the `helmet` and `no_helmet`
classes. Person and two-wheeler context comes from the COCO-pretrained model.

The current helmet model uses the CC BY 4.0
[`shravya11/bike-helmet-dataset`](https://huggingface.co/datasets/shravya11/bike-helmet-dataset).
Only its annotated COCO `train`, `valid`, and `test` splits are used. Convert
them reproducibly with:

```powershell
cd E:\基于YOLO
.\backend\.venv\Scripts\python.exe .\backend\training\prepare_coco.py `
  --source .\data\bike-helmet-repo `
  --output .\data\bike-helmet-yolo
```

The resulting two-class checkpoint (`helmet`, `no_helmet`) is combined at
inference time with `backend/yolo11s.pt` for the `person`, `bicycle`, and
`motorcycle` context classes.

Train on the RTX 4060 with:

```powershell
cd E:\基于YOLO\backend
.\.venv\Scripts\python.exe .\training\train.py `
  --data E:\基于YOLO\data\bike-helmet-yolo\dataset.yaml `
  --base .\yolo11s.pt --epochs 100 --imgsz 640 --batch 8
```

Copy the resulting `weights/best.pt` to `backend/models/best.pt` and restart
the backend. Validate on a held-out test set before using the output as an
enforcement lead. Precision, recall, mAP50-95, per-class confusion matrices,
night/rain performance, and false-positive rate must all be reported.

The system intentionally does not infer a helmet violation from the absence of
a helmet box. It requires a positive `no_helmet` detection, and every generated
event is marked for manual review.

