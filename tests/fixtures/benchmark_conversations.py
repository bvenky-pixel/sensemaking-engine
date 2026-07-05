"""
Fixed benchmark inputs for validating the Interpretation Engine (see
engine/decisions.md v1.0 exit criteria, "Stable across repeated runs on
the fixed benchmark conversations (TC1: boss/product-team pivot; TC2:
toxic boss/HR/weak job market)").

CAVEAT: the original TC1/TC2 wording used during the v1.0 n=10/n=20
testing rounds was never checked into the repo -- it only lived in
gitignored test-runs/ output and shell scrollback, both since lost. The
text below is a best-effort RECONSTRUCTION from fragments directly quoted
in engine/decisions.md (e.g. "he keeps side stepping it," "boss is not
willing to grant me the move," "HR has not been very supportive," "weak
job market"), not a recovered original. Treat any comparison against the
old thresholds as approximate until/unless corrected.

If you find the real originals, replace these and remove this caveat.
Either way, keep this file checked in from now on -- that's the actual
fix for "TC1/TC2 can't be reproduced," not just this one reconstruction.
"""

TC1 = (
    "My boss is not willing to grant me the move to the product team. "
    "He keeps side stepping the conversation whenever I bring it up. "
    "I don't know if I should leave the company or do something else."
)

TC2 = (
    "My boss is toxic and HR has not been very supportive. "
    "The job market is weak right now so I don't know if I should look "
    "for something else."
)

BENCHMARKS = {
    "TC1": TC1,
    "TC2": TC2,
}
