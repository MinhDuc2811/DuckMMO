# Isolated MoneyPrinterTurbo runtime

`uv sync --project integrations/moneyprinter-turbo --frozen --no-dev` installs mpt 1.3.10
in this directory's ignored .venv, separately from the main FastAPI/Streamlit app.
The bridge is application-owned, not a modified/fake MPT renderer. It calls native stock
search/download and video assembly only. Paid generators, TTS, BGM and publishing are not used.

Upstream: https://github.com/harry0703/MoneyPrinterTurbo
Package license: MIT, Copyright (c) 2024 Harry. Dependency/artifact licenses are separate.
See ../../docs/moneyprinter.md for configuration, source provenance, bounds and test scope.
