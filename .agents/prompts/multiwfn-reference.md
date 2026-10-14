# Prompt: extend CP2K input generation with Multiwfn references

Copy this prompt and replace the placeholders.

---

Read `.agents/DEVELOPMENT.md`, `docs/roadmap.md`, `docs/input-generation.md`,
and the third-party provenance/terms records first.
Use English for development, documentation, prompts, comments, messages, and reports
unless the user explicitly requests another communication language.
Preserve original upstream quotations, citations, scientific syntax, paths, and user data.

Long-term goal: fully cover Multiwfn's CP2K input-generation functionality.
Implement only: <one explicit feature or related branch group>
Upstream reference: <version, source path, file, subroutine; verify if uncertain>
Target CP2K version: <version or request confirmation>

Workflow:

1. Confirm the source exists; inspect menus, initialization, and generation branches;
   hash the file. The initial baseline is
   `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`, but do not assume it exists
   elsewhere or make it a runtime dependency.
2. Compare current `inputgen.py`, CLI, structure readers, and tests. Separate
   implemented/partial/missing/version-inapplicable features. Detailed comparisons
   belong in the conversation, not a new comparison document by default.
3. Explain the minimal interface, parameters/units, constraints, compatibility,
   and upstream differences. Upstream defaults are not universally appropriate.
4. Check target-version keywords/nesting, basis/potential names, spin/charge,
   periodicity/solvers, SCF/k-points. Ask about ambiguity/conflicts; do not silently repair physics.
5. Separate generation from exclusive writing. Record complete effective inputs,
   settings, units, citations, and provenance. Do not inherit restart calculation
   settings implicitly; define preservation/conversion when extending KIND semantics.
6. Update `third_party/multiwfn/PROVENANCE.md`: version/file/subroutine/hash,
   actual reference usage, differences, copyright/citation locations, permission,
   and validation boundaries. Preserve historical terms; do not invent permission,
   claim clean-room development, or assume MIT compatibility.
7. Test branches/invalid combinations, section structure, round-trip geometry,
   CLI/hashes/multi-file protection as needed. Synthetic tests do not certify CP2K execution.
8. Update actual support/progress, not the long-term goal as completed.
9. Follow `.agents/prompts/update-version-docs.md` after features. Update the
   software version, changelog, and documentation without conflating schema/CP2K versions.

Do not run CP2K/Multiwfn, overwrite results, or commit/push automatically.
For actual software validation, propose a small independent-directory plan and
obtain authorization first.

Report completed scope, upstream behavior/default differences, provenance,
tests, and remaining gaps.

---

Related: [development rules](../DEVELOPMENT.md), [roadmap](../../docs/roadmap.md),
[third-party notices](../../THIRD_PARTY_NOTICES.md),
[provenance](../../third_party/multiwfn/PROVENANCE.md).
