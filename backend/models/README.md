# Model weights

Place the trained Ultralytics checkpoint at `backend/models/best.pt`, or set
`YOLO_WEIGHTS` to an absolute checkpoint path.

The detector must contain these semantic classes (aliases are accepted by the
backend):

- `electric_bicycle` or `motorcycle` / `bicycle`
- `person` or `rider`
- `helmet`
- `no_helmet` or `bare_head`

The backend deliberately does not treat a missing `helmet` detection as a
violation. A positive `no_helmet` / `bare_head` detection is required. This
reduces false accusations caused by small or occluded heads.

