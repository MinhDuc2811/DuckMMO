# Test runner integrity cases

All cases live in `integration/test_discovery.py`. They launch a separate temporary
pytest project to verify runner behavior; fixture test failures are expected inputs,
not application regressions or replacements for product tests.

| ID | Expected behavior |
| --- | --- |
| TH-I01 | Offline default runs unit fixture, explicitly skips opt-in live fixture, omits browser collection |
| TH-I02 | Feature/layer selection collects only the requested unit fixture |
| TH-I03 | Explicit live fixture failure exits 1 and is not converted to skip |
| TH-I04 | Explicit browser fixture failure exits 1 and is not omitted |
| TH-I05 | Unknown feature exits 5 instead of reporting zero-test success |
