#!/bin/bash
# Test script to diagnose drift issues

CHECKPOINT="${HOME}/unitree_RL/model_10000.pt"

echo "=========================================="
echo "Testing Robot Drift - Multiple Scenarios"
echo "=========================================="
echo ""

echo "1. Testing with randomization DISABLED (clean test)"
echo "   This isolates model behavior from environment randomness"
python scripts/play_straight.py \
  --checkpoint-file="$CHECKPOINT" \
  --linear-velocity-x 0.8 \
  --disable-randomization \
  --viewer viser \
  --num-envs 1 &

PID=$!
echo "   Started viewer (PID: $PID)"
echo "   Open browser to http://localhost:8080"
echo ""
echo "   Watch for:"
echo "   - Does robot drift right consistently?"
echo "   - Check the blue arrow (command) vs cyan arrow (actual velocity)"
echo "   - Press Ctrl+C when done observing"
echo ""

wait $PID

echo ""
echo "2. Next test: Try with randomization ENABLED"
read -p "   Press Enter to continue..."

python scripts/play_straight.py \
  --checkpoint-file="$CHECKPOINT" \
  --linear-velocity-x 0.8 \
  --disable-randomization false \
  --viewer viser \
  --num-envs 1 &

PID=$!
echo "   Started viewer (PID: $PID)"
echo "   If drift is WORSE with randomization, the issue is:"
echo "   - Model didn't see balanced training data"
echo "   Press Ctrl+C when done"
echo ""

wait $PID

echo ""
echo "3. Test complete. Summary:"
echo "   - If drift occurs in BOTH tests: checkpoint needs more training"
echo "   - If drift only with randomization: model overfitted to specific conditions"
echo "   - Small drift (<0.5m over 10m) is normal and acceptable"
