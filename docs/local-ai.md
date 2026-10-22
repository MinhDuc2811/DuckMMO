# Local analysis in this workspace

Runtime: llama.cpp b11796, Windows x64 Vulkan build, bound to 127.0.0.1:8081.
Model: official Qwen/Qwen3-4B-GGUF, Q4_K_M, approximately 2.50 GB.
The downloaded model revision is recorded in data/local-ai/model-revision.txt.
The API uses a randomly generated local key stored under ignored data/local-ai/.
Provider settings are stored in ignored data/settings/analysis.json.

Run `scripts/run-local-ai.ps1` from PowerShell when restarting the local stack.
The model server needs to remain running alongside API, worker and Streamlit.
It loads GPU layers through Vulkan and uses a 16K context with quantized KV cache.
Reasoning is disabled for narration generation. Structured JSON output is enabled
for this connection, with a 4096-token output cap and 300-second request timeout.
A model response must still pass the usual analysis schema validation.
No source text is sent to an external AI provider by this setup.

This is a small local model, so factual accuracy and Vietnamese wording still need
human review. Very long inputs may exceed its context and fail rather than silently
being truncated or passed through as analysed text.

Official sources:
- https://github.com/ggml-org/llama.cpp/releases/tag/b11796
- https://huggingface.co/Qwen/Qwen3-4B-GGUF

Expected SHA256 values verified before running:
- llama-b11796-bin-win-vulkan-x64.zip:
  b7035131edd2dcfc4a123a9deb16d109af655ef7c5e0d283edd7323808cb78b7
- Qwen3-4B-Q4_K_M.gguf:
  7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5
