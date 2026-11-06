# Native CUBE excerpt provenance and privacy boundary

`excerpts.json` contains **verbatim selected lines only**, not complete CP2K logs
or CUBEs. Eleven source records cover six stdout selections and five CUBE headers.
Full grids, wavefunctions, private stderr/accounting, execution timestamps, host/
account information, scheduler IDs and local filesystem paths are not distributed.

Each source preserves its original full-file SHA-256 and byte size, calculated
before selection. Every included line retains its original 1-based line number.
Execution timestamp rows and other private sections were omitted, not replaced by
invented successful records. Source `path` values beginning `native-format/` are
explicit non-filesystem aliases for these selections; they are not public source
URLs or claims that original evidence exists at those paths. The original source
mapping remains private. Tests do not require private files or network access.

- Stdout selections retain version, main/outer SCF, virtual block headers, explicit
  eigensolver convergence, FORCE_EVAL energy and warning count formatting. The
  older banner explicitly says Development Version. Selected convergence records
  do not establish process exit or complete native acceptance.
- CUBE selections retain only the first nine lines: comments, origin/count, grid
  vectors and atom rows. They preserve actual zero/nonzero auxiliary fields,
  UKS total-density title and orbital/spin labels. No scalar payload is included.
  Header-only selections cannot pass full CUBE validation.
- Failed/successful scheduler and signal scenarios use independently constructed
  **synthetic** text in the tests, not redacted private accounting presented as
  original evidence. No particular CP2K build/compiler defect is asserted.

A test-only sparse-text adapter inserts blank placeholders to exercise the shared
parser at original line numbers. These reconstructed files are incomplete excerpt
adapters, not full outputs; their hashes are not the original source hashes.
Complete tiny fields in other tests are synthetic, not resampled native grids.

Source versions, near-integer integrals and passing tests do not certify an
installation or scientific accuracy. Existing CP2K and
[Multiwfn reference/terms](../../../third_party/multiwfn/PROVENANCE.md) remain
applicable; no source port or additional license grant is claimed.
