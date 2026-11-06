"""Offline example audit tests: synthetic bundles and provenance-tagged excerpts."""
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cp2kkit.cube import CubeReader
from cp2kkit.errors import AmbiguousProject, KitError, OutputExists, ParseError
from cp2kkit.parser import parse_output
from cp2kkit.structure import BOHR_TO_ANGSTROM
from tests.synthetic_cp2k_data import basis_entry, potential_entry
from tests.test_cube_validation_preparation import prep

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'examples/cube-validation/audit.py'
spec = importlib.util.spec_from_file_location('cube_audit_example', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
FIXTURE = ROOT/'tests/fixtures/cube-native-041/excerpts.json'


def sparse_excerpt(lines):
    """Test adapter only: blanks for omitted lines, never a claimed full output."""
    result = ['']*max(row['line'] for row in lines)
    for row in lines:
        result[row['line']-1] = row['text']
    return '\n'.join(result)+'\n'


class CubeAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='cp2kkit-audit-test-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        data = self.root/'data'
        data.mkdir()
        (data/'BASIS_MOLOPT').write_text(''.join(basis_entry(el, f'DZVP-MOLOPT-SR-GTH-q{q}')
                                               for el,q in (('H',1),('O',6))))
        (data/'GTH_POTENTIALS').write_text(''.join(potential_entry(el,q,f'GTH-PBE-q{q}')
                                                 for el,q in (('H',1),('O',6))))
        with redirect_stdout(io.StringIO()):
            prep.prepare(data, self.root/'prepared')
        self.run = self.root/'run'
        self.run.mkdir()
        (self.run/'water.inp').write_bytes((self.root/'prepared/01-rks-ot/water.inp').read_bytes())
        (self.run/'water.out').write_text(
            ' CP2K| version string: CP2K version 2026.2\n GLOBAL| Run type  ENERGY\n'
            ' *** SCF run converged in 16 steps ***\n outer SCF loop converged in 1 iterations\n'
            ' Using OT eigensolver for additional unoccupied orbitals spin 1\n'
            ' Lowest Eigenvalues of the unoccupied subspace spin 1\n'
            ' OT| Eigensolver reached convergence in 111 iterations\n'
            ' ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] -1.0\n PROGRAM ENDED AT synthetic\n')
        (self.run/'water.err').write_text('')
        self.scheduler = self.root/'accounting.txt'
        self.scheduler.write_text('JobID|State|ExitCode|DerivedExitCode\n'
                                  '123|COMPLETED|0:0|0:0\n123.batch|COMPLETED|0:0|\n')
        self.case = {'id':'sample', 'preparation_matrix':'prepared/case-matrix.json',
                     'preparation_case':'01-rks-ot', 'input':'run/water.inp',
                     'data_directory':'prepared/01-rks-ot', 'stdout':'run/water.out',
                     'stderr':'run/water.err', 'cube_directory':'run',
                     'scheduler':'accounting.txt', 'job_id':'123'}
        for name,title in [('ELECTRON_DENSITY','ELECTRON DENSITY'),
                           ('v_hartree','HARTREE POTENTIAL'),
                           ('WFN_00004_1','WAVEFUNCTION 4 spin 1'),
                           ('WFN_00005_1','WAVEFUNCTION 5 spin 1')]:
            self.cube(name,title)
        self.output = self.root/'new-audit'
        self.plan = self.root/'plan.json'

    def cube(self, name, title, fields=(6,1,1)):
        # Hand-written four-point field at the prepared geometry, NOT native data.
        lines = ['-Quickstep-',title,'3 0 0 0','2 1 0 0','1 0 1 0','2 0 0 1']
        for z,field,position in zip((8,1,1),fields,((8,8,8),(8.757,8,8.586),(7.243,8,8.586))):
            lines.append(f'{z} {field} '+' '.join(str(v/BOHR_TO_ANGSTROM) for v in position))
        lines.append('1 -1 2 -2')
        path = self.run/f'water-{name}-1_0.cube'
        path.write_text('\n'.join(lines)+'\n')
        return path

    def execute(self):
        self.plan.write_text(json.dumps({'format':'cube-audit-plan-v1','cases':[self.case]}))
        return audit.audit(self.plan,self.output)['cases'][0]

    def test_separate_evidence_identity_and_determinism(self):
        original = {p:p.read_bytes() for p in self.run.iterdir()}
        self.case['checksums'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        result = self.execute()
        self.assertTrue(result['clean_exit'])
        self.assertTrue(result['main_scf_converged'])
        self.assertTrue(result['outer_scf_converged'])
        self.assertTrue(result['virtual_eigensolver']['converged'])
        self.assertEqual(result['virtual_eigensolver']['blocks'][0]['iterations'],111)
        self.assertIsNone(result['process'])  # Scheduler status is not a process capture.
        self.assertEqual(result['actual_cube_count'],4)
        self.assertTrue(all(v is True for k,v in result['checks'].items() if k!='data_identity'))
        self.assertEqual(result['checks']['data_identity'],[True,True])
        self.assertIsNone(result['scientific_validation_passed'])
        for entry in result['cubes']:
            if 'WFN_' in entry['filename'] or 'v_hartree' in entry['filename']:
                self.assertEqual(entry['report']['scalar_type'],'unknown')
                self.assertEqual(entry['report']['scalar_unit'],'unknown')
        first=(self.output/'results.json').read_bytes()
        second=self.root/'another-audit'
        audit.audit(self.plan,second)
        self.assertEqual(first,(second/'results.json').read_bytes())
        self.assertEqual(original,{p:p.read_bytes() for p in self.run.iterdir()})

    def test_late_signal_and_failed_scheduler_do_not_erase_convergence(self):
        (self.run/'water.err').write_text('Program received signal SIGSEGV\n')
        self.scheduler.write_text('JobID|State|ExitCode|DerivedExitCode\n'
                                  '123|FAILED|11:0|0:0\n123.batch|FAILED|11:0|\n')
        result=self.execute()
        self.assertFalse(result['clean_exit'])
        self.assertTrue(result['program_ended'])
        self.assertTrue(result['main_scf_converged'])
        self.assertTrue(result['virtual_eigensolver']['converged'])
        self.assertTrue(result['checks']['cube_format'])
        self.assertEqual(result['scheduler']['job']['fields']['DerivedExitCode'],'0:0')
        self.assertIsNone(result['process'])

    def test_uks_channel_specific_requests_and_two_virtual_blocks(self):
        self.case['preparation_case']='03-uks-ot'
        self.case['data_directory']='prepared/03-uks-ot'
        (self.run/'water.inp').write_bytes((self.root/'prepared/03-uks-ot/water.inp').read_bytes())
        self.cube('ELECTRON_DENSITY','SUM OF ALPHA AND BETA DENSITY')
        self.cube('SPIN_DENSITY','SPIN DENSITY')
        self.cube('WFN_00003_2','WAVEFUNCTION 3 spin 2')
        self.cube('WFN_00004_2','WAVEFUNCTION 4 spin 2')
        out=self.run/'water.out'
        out.write_text(out.read_text().replace(' ENERGY|',
            ' Lowest Eigenvalues of the unoccupied subspace spin 2\n'
            ' OT| Eigensolver reached convergence in 53 iterations\n ENERGY|'))
        result=self.execute()
        self.assertEqual(result['actual_cube_count'],7)
        self.assertTrue(result['checks']['requests_match'])
        self.assertTrue(result['virtual_eigensolver']['converged'])
        self.assertEqual(result['expected_mo_spin_pairs'],[(3,2),(4,1),(4,2),(5,1)])

    def test_diagonalization_is_explicitly_not_ot_virtual_convergence(self):
        self.case['preparation_case']='02-rks-diag'
        self.case['data_directory']='prepared/02-rks-diag'
        (self.run/'water.inp').write_bytes((self.root/'prepared/02-rks-diag/water.inp').read_bytes())
        self.cube('WFN_00003_1','WAVEFUNCTION 3 spin 1')
        self.cube('WFN_00006_1','WAVEFUNCTION 6 spin 1')
        (self.run/'water.out').write_text(
            ' CP2K| version string: CP2K version 2026.2\n'
            ' *** SCF run converged in 22 steps ***\n'
            ' ENERGY| Total FORCE_EVAL ( QS ) energy [hartree] -1.0\n PROGRAM ENDED AT synthetic\n')
        result=self.execute()
        self.assertTrue(result['checks']['requests_match'])
        self.assertEqual(result['requested_settings']['added_mos'],2)
        self.assertIsNone(result['virtual_eigensolver']['converged'])
        self.assertIn('not_applicable',result['virtual_eigensolver'])
        self.assertIsNone(result['outer_scf_converged'])

    def test_missing_and_pending_evidence_never_pass(self):
        self.scheduler.write_text('JobID|State|ExitCode\n123|RUNNING|0:0\n123.batch|RUNNING|0:0\n')
        (self.run/'water.err').unlink()
        result=self.execute()
        self.assertIsNone(result['clean_exit'])
        self.assertIsNone(result['scheduler']['clean_exit'])
        self.assertIsNone(result['checks']['provided_checksums_match'])
        self.assertTrue(result['errors'])

    def test_missing_virtual_and_main_evidence_unknown(self):
        (self.run/'water.out').write_text(' CP2K| version string: CP2K version 2026.2\n')
        result=self.execute()
        self.assertIsNone(result['main_scf_converged'])
        self.assertIsNone(result['outer_scf_converged'])
        self.assertIsNone(result['program_ended'])
        self.assertIsNone(result['virtual_eigensolver']['converged'])
        self.assertIsNone(result['clean_exit'])

    def test_earlier_scf_failure_not_hidden_by_final_convergence(self):
        p=self.run/'water.out'
        p.write_text(' SCF run NOT converged\n'+p.read_text())
        self.assertFalse(self.execute()['main_scf_converged'])

    def test_explicit_process_status_zero_negative_unknown_and_malformed(self):
        for code,expected in [(0,True),(-11,False),(None,None)]:
            with self.subTest(code=code):
                status=self.root/'process.json'
                status.write_text(json.dumps({'returncode':code}))
                self.case['process_status']='process.json'
                result=audit.audit_case(self.case,self.root)
                self.assertIs(result['clean_exit'],expected)
                self.assertEqual(result['process']['returncode'],code)
        status.write_text('{"returncode": false}')
        with self.assertRaises(ParseError):
            audit.audit_case(self.case,self.root)

    def test_hash_mismatch_missing_checksums_and_wrong_input_not_default_success(self):
        (self.run/'water.inp').write_text('wrong input')
        self.case['checksums']={'water.out':'0'*64,'absent.cube':'1'*64}
        result=self.execute()
        self.assertFalse(result['checks']['input_identity'])
        self.assertFalse(result['checks']['provided_checksums_match'])
        self.assertEqual(result['missing_checksum_files'],['absent.cube'])
        self.assertTrue(result['checks']['generator_identity'])
        # Exit classification is deliberately independent of identity/accuracy.
        self.assertTrue(result['clean_exit'])
        self.assertIsNone(result['scientific_validation_passed'])

    def test_missing_data_and_generator_identity_are_reported(self):
        # Remove only this isolated synthetic copy, not any scientific source.
        (self.root/'prepared/data/GTH_POTENTIALS').unlink()
        manifest_path=self.root/'prepared/01-rks-ot/water.inp.json'
        manifest=json.loads(manifest_path.read_text())
        manifest['input_text']+='changed generator text\n'
        manifest_path.write_text(json.dumps(manifest))
        result=self.execute()
        self.assertFalse(result['checks']['generator_identity'])
        self.assertIn(None,result['checks']['data_identity'])
        self.assertTrue(result['errors'])

    def test_atom_auxiliary_fields_not_grid_identity(self):
        self.cube('WFN_00004_1','WAVEFUNCTION 4 spin 1',fields=(0,0,0))
        result=self.execute()
        self.assertTrue(result['checks']['grid_match'])
        fields=[entry['report']['atoms'][0]['atom_field'] for entry in result['cubes']]
        self.assertIn(0,fields)
        self.assertIn(6,fields)

    def test_missing_duplicate_wrong_spin_and_header_orbital_labels(self):
        p=self.run/'water-WFN_00005_1-1_0.cube'
        p.unlink()
        result=audit.audit_case(self.case,self.root)
        self.assertFalse(result['checks']['requests_match'])
        self.cube('WFN_00005_2','WAVEFUNCTION 5 spin 2')
        self.assertFalse(audit.audit_case(self.case,self.root)['checks']['requests_match'])
        self.cube('WFN_00005_1','WAVEFUNCTION 4 spin 1')
        self.assertFalse(audit.audit_case(self.case,self.root)['checks']['requests_match'])
        self.cube('WFN_00005_1','WAVEFUNCTION 5 spin 1')
        (self.run/'water-WFN_00005_2-1_0.cube').unlink()
        (self.run/'water-WFN_00005_1-2_0.cube').write_bytes((self.run/'water-WFN_00005_1-1_0.cube').read_bytes())
        self.assertFalse(audit.audit_case(self.case,self.root)['checks']['requests_match'])

    def test_truncated_nonfinite_and_grid_geometry_failures(self):
        path=self.run/'water-WFN_00004_1-1_0.cube'
        original=path.read_text()
        for values in ('1 2','1 nan 2 3'):
            path.write_text('\n'.join(original.splitlines()[:-1]+[values])+'\n')
            result=audit.audit_case(self.case,self.root)
            self.assertFalse(result['checks']['cube_format'])
            self.assertIsNone(result['checks']['grid_match'])
            self.assertTrue(result['errors'])
        path.write_text(original.replace('3 0 0 0','3 1 0 0',1))
        self.assertFalse(audit.audit_case(self.case,self.root)['checks']['grid_match'])
        path.write_text(original.replace('8 6 ','7 6 ',1))
        self.assertFalse(audit.audit_case(self.case,self.root)['checks']['geometry_match'])

    def test_missing_cube_directory_and_empty_directory_are_distinct(self):
        self.case['cube_directory']='missing'
        result=audit.audit_case(self.case,self.root)
        self.assertIsNone(result['actual_cube_count'])
        self.assertIsNone(result['checks']['requests_match'])
        (self.root/'missing').mkdir()
        result=audit.audit_case(self.case,self.root)
        self.assertEqual(result['actual_cube_count'],0)
        self.assertFalse(result['checks']['requests_match'])

    def test_multiple_segments_refused_and_failed_publication_cleaned(self):
        out=self.run/'water.out'
        out.write_text(out.read_text()+' CP2K| version string: another segment\n')
        with self.assertRaises(AmbiguousProject):
            self.execute()
        self.assertFalse((self.output/'results.json').exists())
        self.assertEqual(list(self.output.iterdir()),[])

    def test_output_collision_dangling_symlink_and_publication_failure(self):
        self.output.mkdir()
        sentinel=self.output/'old.wfn'
        sentinel.write_text('preserve')
        with self.assertRaises(OutputExists):
            self.execute()
        self.assertEqual(sentinel.read_text(),'preserve')
        self.output=self.root/'dangling'
        self.output.symlink_to(self.root/'absent')
        with self.assertRaises(OutputExists):
            self.execute()
        self.output=self.root/'publication-error'
        with patch('cp2kkit.io.os.link',side_effect=OSError('injected publication failure')):
            with self.assertRaisesRegex(OSError,'injected publication failure'):
                self.execute()
        self.assertEqual(list(self.output.iterdir()),[])

    def test_bad_plans_and_nonfinite_metadata_fail_without_publication(self):
        for plan in ([], {'format':'other','cases':[self.case]},
                     {'format':'cube-audit-plan-v1','cases':[]},
                     {'format':'cube-audit-plan-v1','cases':[dict(self.case, typo='bad')]},
                     {'format':'cube-audit-plan-v1','cases':[dict(self.case,job_id=None)]}):
            self.plan.write_text(json.dumps(plan))
            with self.assertRaises(ParseError): audit.audit(self.plan,self.output)
            self.assertFalse(self.output.exists())
        self.plan.write_text('{"format": "cube-audit-plan-v1", "cases": NaN}')
        with self.assertRaises(ParseError): audit.audit(self.plan,self.output)
        self.assertFalse(self.output.exists())

    def test_example_subprocess_creates_report_without_executors(self):
        self.plan.write_text(json.dumps({'format':'cube-audit-plan-v1','cases':[self.case]}))
        proc=subprocess.run([sys.executable,str(SCRIPT),'--plan',str(self.plan),
                             '--output',str(self.output)],capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertTrue((self.output/'results.json').exists())
        collision=subprocess.run([sys.executable,str(SCRIPT),'--plan',str(self.plan),
                                  '--output',str(self.output)],capture_output=True,text=True)
        self.assertEqual(collision.returncode,5,collision.stderr)


class NativeExcerptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.sources=json.loads(FIXTURE.read_text())['sources']

    def test_original_identity_and_line_locators_are_explicit(self):
        self.assertEqual(len(self.sources),11)
        self.assertTrue(all(s['source']['path'].startswith('native-format/') for s in self.sources))
        self.assertEqual({s['kind'] for s in self.sources}, {'stdout', 'cube_header'})
        for source in self.sources:
            self.assertRegex(source['source']['sha256'],r'^[0-9a-f]{64}$')
            self.assertGreater(source['source']['size_bytes'],0)
            numbers=[r['line'] for r in source['lines']]
            self.assertEqual(numbers,sorted(set(numbers)))
            self.assertTrue(all(type(n) is int and n>0 for n in numbers))

    def test_real_versions_main_scf_and_virtual_spin_blocks(self):
        stdout=[s for s in self.sources if s['kind']=='stdout']
        self.assertEqual(len(stdout),6)
        for source in stdout:
            path=self.root/'excerpt.out'
            path.write_text(sparse_excerpt(source['lines']))
            run=parse_output(path)
            self.assertEqual(len(run.segments),1)
            self.assertTrue(run.segments[0].scf_converged)
            # Timestamp-bearing termination rows are omitted for publication.
            self.assertFalse(run.segments[0].completed)
            version='2025.2' if '/2025.2/' in source['source']['path'] else '2026.2'
            self.assertIn(version,run.software_version)
            if version=='2025.2': self.assertIn('Development Version',run.software_version)
            lines=[{'path':source['source']['path'],**r} for r in source['lines']]
            if '02-rks-diag' in source['source']['path']:
                self.assertIsNone(audit.virtual_evidence(lines,[1])['converged'])
            else:
                spins=[1,2] if '03-uks-ot' in source['source']['path'] else [1]
                virtual=audit.virtual_evidence(lines,spins)
                self.assertTrue(virtual['converged'])
                self.assertEqual([b['iterations'] for b in virtual['blocks']],
                                 [87,53] if len(spins)==2 else [111])
                evidence=virtual['blocks'][0]['evidence'][-1]
                self.assertIn(evidence['line'],[r['line'] for r in source['lines']])

    def test_synthetic_failed_derived_zero_and_clean_accounting(self):
        # Deliberately synthetic: no private scheduler identities or diagnostics.
        path=self.root/'accounting.txt'
        path.write_text('JobID|State|ExitCode|DerivedExitCode\n'
                        '100|FAILED|11:0|0:0\n100.batch|FAILED|11:0|\n'
                        '101|COMPLETED|0:0|0:0\n101.batch|COMPLETED|0:0|\n')
        result=audit.accounting(path,'100')
        self.assertFalse(result['clean_exit'])
        self.assertEqual(result['job']['fields']['DerivedExitCode'],'0:0')
        self.assertEqual(result['job']['fields']['ExitCode'],'11:0')
        self.assertTrue(audit.accounting(path,'101')['clean_exit'])
        for text in ('Program received signal SIGSEGV', 'process exited on signal 9'):
            self.assertIsNotNone(audit.FATAL.search(text))

    def test_real_cube_headers_preserve_auxiliary_fields_and_unknown_mos(self):
        headers=[]
        for source in [s for s in self.sources if s['kind']=='cube_header']:
            path=self.root/'header.cube'
            path.write_text(sparse_excerpt(source['lines']))
            with CubeReader(path) as reader:
                self.assertFalse(reader.finished)
                report={key:getattr(reader,key) for key in ('shape','origin','vectors','length_unit','atoms')}
                headers.append(report)
                self.assertEqual(reader.shape,[200,200,200])
                if 'WFN_' in source['source']['path']:
                    self.assertEqual(reader.scalar_type,'unknown')
                    self.assertEqual(reader.scalar_unit,'unknown')
                if '03-uks-ot/water-ELECTRON' in source['source']['path']:
                    self.assertEqual(reader.scalar_type,'electron-density')
                with self.assertRaises(KitError):
                    reader.report(None)  # Header-only excerpt cannot pass EOF integrity.
        self.assertTrue(all(audit.grid_signature(r)==audit.grid_signature(headers[0]) for r in headers))
        self.assertEqual(headers[0]['atoms'][0]['atom_field'],6)
        self.assertEqual(headers[1]['atoms'][0]['atom_field'],0)
        self.assertEqual(headers[2]['atoms'][0]['atom_field'],0)

    def test_virtual_missing_failure_and_duplicate_spin_cannot_pass(self):
        lines=[{'path':'synthetic','line':1,'text':'Lowest Eigenvalues of the unoccupied subspace spin 1'},
               {'path':'synthetic','line':2,'text':'OT| Eigensolver reached convergence in 4 iterations'}]
        self.assertTrue(audit.virtual_evidence(lines,[1])['converged'])
        self.assertIsNone(audit.virtual_evidence(lines,[1,2])['converged'])
        self.assertIsNone(audit.virtual_evidence(lines+lines,[1])['converged'])
        self.assertIsNone(audit.virtual_evidence(lines[1:],[1])['converged'])
        lines.append({'path':'synthetic','line':3,'text':'OT| Eigensolver did not converge'})
        self.assertFalse(audit.virtual_evidence(lines,[1])['converged'])

    def test_accounting_missing_pending_malformed_and_duplicate_are_not_success(self):
        path=self.root/'accounting'
        for text in ('JobID|State|ExitCode\n123|PENDING|0:0\n',
                     'JobID|State|ExitCode\n123|COMPLETED|0:0\n',
                     'JobID|State|ExitCode\n123|COMPLETED|\n123.batch|COMPLETED|\n'):
            path.write_text(text)
            self.assertIsNone(audit.accounting(path,'123')['clean_exit'])
        for text,error in [('JobID|State|ExitCode\n123|COMPLETED|bad\n',ParseError),
                           ('JobID|State|ExitCode\n123|FAILED|1:0\n123|FAILED|1:0\n',AmbiguousProject),
                           ('JobID|State|ExitCode\n123|FAILED\n',ParseError),
                           ('no header',ParseError)]:
            path.write_text(text)
            with self.assertRaises(error): audit.accounting(path,'123')


if __name__=='__main__':
    unittest.main()
