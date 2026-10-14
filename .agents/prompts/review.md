# Prompt: review code and scientific settings

Copy this prompt and replace the placeholders.

---

Read `.agents/DEVELOPMENT.md` and perform a read-only review.
Use English for review reports and development text unless the user explicitly
requests another communication language. Preserve original quoted evidence,
citations, scientific syntax, paths, and user data.

Scope: <files, features, current diff, or commit>
Focus: <correctness, compatibility, science, overwrite protection, provenance, tests>

Requirements:

1. Inspect actual code, callers, tests, documentation, and applicable third-party
   records; do not infer correctness from descriptions alone.
2. Prioritize wrong results, silently lost settings, overwritten data, false passed
   assessments, nondeterministic selection, unit confusion, injection, and CLI/API regressions.
3. For generation check software/version, method/basis/potential, dispersion,
   charge/multiplicity/KIND, PBC/Poisson/cell, SCF/k-points/smearing, constraints,
   and source-inheritance semantics.
4. Review upstream versions/files/hashes, actual use, and notices. Citations,
   public source, or a language rewrite do not automatically grant extra permission.
5. Give each finding a severity, file/line, evidence, trigger, impact, and minimal fix.
   Separate certain defects from risks requiring verification.
6. If no definite defects are found, say so and list testing/runtime-validation gaps.
7. Do not modify files, install packages, start calculations, or commit/push automatically.
   Existing tests with temporary outputs may be run; report exactly what ran.

List findings first, then validation and remaining risks.

---

Related: [development rules](../DEVELOPMENT.md), [schema](../../docs/schema.md).
