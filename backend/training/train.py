from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the Wuhan e-bike violation detector")
    parser.add_argument("--data", type=Path, required=True, help="YOLO dataset YAML")
    parser.add_argument("--base", default="yolo11s.pt", help="Ultralytics base checkpoint")
    parser.add_argument(
        "--resume",
        type=Path,
        help="Resume an interrupted run from a last.pt checkpoint",
    )
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8, help="Use -1 for automatic batch sizing")
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=0, help="Use 0 on Windows to avoid DataLoader memory failures")
    parser.add_argument("--project", default="runs/violation")
    parser.add_argument("--name", default="yolo11s-wuhan-ebike")
    parser.add_argument("--exist-ok", action="store_true", help="Reuse the named run directory")
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--plots", action="store_true", help="Generate training plots (uses extra system memory)")
    parser.add_argument("--mosaic", type=float, default=0.0)
    parser.add_argument("--lr0", type=float, default=0.01)
    parser.add_argument("--lrf", type=float, default=0.01)
    parser.add_argument("--warmup-epochs", type=float, default=3.0)
    parser.add_argument("--close-mosaic", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.data.exists():
        raise SystemExit(f"Dataset config does not exist: {args.data}")
    if args.resume and not args.resume.exists():
        raise SystemExit(f"Resume checkpoint does not exist: {args.resume}")

    checkpoint = args.resume if args.resume else args.base
    model = YOLO(str(checkpoint))
    if args.resume:
        # Ultralytics restores the epoch, optimizer, scheduler and original
        # training arguments. Batch size is intentionally overridable so an
        # interrupted GPU run can resume with lower thermal/memory pressure.
        model.train(
            resume=str(args.resume),
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
            workers=args.workers,
        )
        return

    model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=args.project,
        name=args.name,
        exist_ok=args.exist_ok,
        patience=args.patience,
        pretrained=True,
        amp=True,
        lr0=args.lr0,
        lrf=args.lrf,
        warmup_epochs=args.warmup_epochs,
        close_mosaic=args.close_mosaic,
        mosaic=args.mosaic,
        cache=False,
        plots=args.plots,
    )


if __name__ == "__main__":
    main()
