# Surface density validation boundaries (0.4.0)

The [preparation example](../examples/surface-density/README.md) constructs
H2O, NH3 and CO2 on a small h-BN model using the existing whole/A/B generator.
It prepares fixed-geometry ENERGY inputs only; no execution or submission occurs.
Model generation is not an optimized adsorption structure, convergence study,
adsorption energy or Bader-charge result.

## Native format compatibility

CP2K v2026.2
[`realspace_grid_cube.F`](https://github.com/cp2k/cp2k/blob/v2026.2/src/pw/realspace_grid_cube.F)
declares 13-character scientific fields and `(6E13.5E3)`. Negative values can
abut the preceding exponent, for example:

```text
 0.15288E-012-0.17851E-009-0.35427E-009-0.12758E-009
```

The reader accepts ordinary whitespace-separated scalars first. Only for
recognized/asserted CP2K does its fallback accept complete 13-character fields
with five mantissa decimals and three exponent digits, at most six per line.
It never splits arbitrary adjacent numbers, skips garbage or repairs NaN/Inf.
Synthetic regressions cover valid adjacency and malformed/non-finite fields.
No upstream Fortran implementation or production density payload is distributed.

## Density-chain acceptance

Before whole-minus-fragments subtraction, verify complete finite fields, matching
grids/origins, compatible geometry, explicit charge/spin/reference states and actual
input/data identities. Do not infer compatibility from filenames or expected
electron totals. Use new paths for differences and derived profiles.

Native-grid profiles integrate full voxels, with perpendicular spacing for skew
cells. The final cumulative profile must agree with the independently accumulated
three-dimensional integral within a justified numerical tolerance. Regression
tests cover unequal dimensions, every axis, cancellation, negative spin integrals
and exclusive-output cleanup on overflow.

Near-zero whole-space differences do not establish zero interfragment transfer.
Positive/negative integrals are not atomic/fragment net charges. File integrity
and arithmetic checks do not establish clean process exit, physical reference
fitness, cell/grid/basis convergence or adsorption accuracy.

## Public/private boundary

Private execution details, scheduler identities, installation diagnostics and raw
scientific results are not part of the repository distribution. Their absence
does not establish acceptance or imply a defect in a particular CP2K release.
Actual calculations require separate authorization and fresh run directories.
