# Responsible AI

Quorava calls its anomaly component "AI-assisted" only in the operational sense: it prioritizes unusual records for expert review. The implementation is deterministic and inspectable.

## Model card

- **Version:** `robust-rules-v1.0`
- **Purpose:** rank revenue events for human review.
- **Inputs:** normalized amount, margin, discount and quality confidence.
- **Method:** median absolute deviation plus transparent policy thresholds.
- **Output:** risk score, severity, evidence and a recommended review action.
- **Prohibited use:** autonomous approval, rejection, posting, payment, customer action or fraud accusation.

## Limitations

The synthetic dataset is small and not representative of a real business distribution. Thresholds are illustrative. Production use requires historical back-testing, segment-specific calibration, bias review, drift monitoring, reviewer feedback, documented overrides and accountable model ownership.

