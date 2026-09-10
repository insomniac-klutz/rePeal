"""Phase 1.5 walking skeleton: a throwaway end-to-end slice (~100 cases -> LLM
extraction -> minimal DuckDB -> logreg -> one static page -> one command).

See OQ.md's "Phase 1.5 -- Walking skeleton" section (tag s:53ce5611). Nothing under
this package is a load-bearing design: it exists to find what breaks at the seams
between ingest and the real Phase 2-4 pipeline, and every module here is expected to
be superseded, phase by phase, once the real thing lands.
"""

from __future__ import annotations
