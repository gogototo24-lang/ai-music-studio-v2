# Thin discovery entrypoint for RunPod GitHub integration.
# The real implementation lives in providers/runpod_yue2_handler.py.

from providers.runpod_yue2_handler import handler
import runpod

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
