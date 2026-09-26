#!/bin/bash
# Health check script for AI Music Studio v2

BASE_URL="${1:-http://localhost:8000}"

echo "Checking AI Music Studio v2 health..."
echo "URL: $BASE_URL"
echo ""

RESPONSE=$(curl -s "$BASE_URL/health")

if [ $? -ne 0 ]; then
    echo "❌ Connection failed. Is the server running?"
    exit 1
fi

echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

echo ""

# Parse response
OK=$(echo "$RESPONSE" | grep -o '"ok":\s*true' | wc -l)
FFMPEG=$(echo "$RESPONSE" | grep -o '"ffmpeg":\s*true' | wc -l)
MUSICGEN=$(echo "$RESPONSE" | grep -o '"musicgen":\s*true' | wc -l)

echo "Status Summary:"
echo "  Server: $([ $OK -eq 1 ] && echo '✓ OK' || echo '❌ Error')"
echo "  FFmpeg: $([ $FFMPEG -eq 1 ] && echo '✓ Available' || echo '❌ Not available')"
echo "  MusicGen: $([ $MUSICGEN -eq 1 ] && echo '✓ Available' || echo '⚠ Not available (using FFmpeg fallback)')"
