# Guardrails — reskin-pipeline
# Add pitfalls discovered during ralph loop iterations here.
# Format: ## Title, **Trigger/Do/Don't/Context**

## Import paths for scripts/reskin/ modules
**Trigger:** Tests or CLI scripts fail with ModuleNotFoundError
**Do:** Use sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))) before imports
**Don't:** Assume scripts/reskin/ is on PYTHONPATH
**Context:** These scripts are not a proper Python package — they live under scripts/ in a C++ repo

## Playwright SharedArrayBuffer
**Trigger:** OpenRCT2 web fails to load in headless Chromium
**Do:** Launch with --enable-features=SharedArrayBuffer and serve with COOP/COEP headers
**Don't:** Use default Chromium launch — SharedArrayBuffer is gated behind cross-origin isolation
**Context:** serve-emscripten.py already sets the right headers. Playwright needs the browser args too.

## fal_client import
**Trigger:** generate_restyled.py imported in tests where fal_client may not be configured
**Do:** Handle fal_client import gracefully (set to None if ImportError)
**Don't:** Crash on import — non-API functions should be testable without FAL_KEY
