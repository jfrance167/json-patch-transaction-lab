import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from patch_lab import contract
from patch_lab.contract import LabError, Unsupported, parse, validate, LIMITS, SCHEMA
from patch_lab.model import analyze, render, _apply, _clone

ROOT = Path(__file__).resolve().parents[1]
FROZEN = json.loads((ROOT / 'fixtures/oracles.json').read_text())


def env(target=None, ops=None, schema=SCHEMA):
    return {'schema':schema,'target':target,'operations':[] if ops is None else ops}


def selected(label):
    return next(c for c in FROZEN['cases'] if c['label']==label)


class ModelTests(unittest.TestCase):
    def test_full_original_reports(self):
        for case in FROZEN['cases']:
            with self.subTest(case=case['label']):
                source=copy.deepcopy(case['input'])
                report,code=analyze(source)
                self.assertEqual(report,case['expected'])
                self.assertEqual(code,case['exit'])
                self.assertEqual(source,case['input'])
                self.assertEqual(json.loads(render(report)),case['expected'])
                self.assertEqual(render(report),json.dumps(case['expected'],ensure_ascii=True,sort_keys=True,allow_nan=False,separators=(',',':'))+'\n')

    def test_fixed_diagnostics(self):
        for case in FROZEN['errors']:
            if case['label']=='raw-output-amplification':continue
            with self.subTest(case=case['label']):
                with self.assertRaises(Unsupported if case['exit']==3 else LabError) as caught:
                    analyze(parse(case['raw'].encode('utf-8')))
                self.assertEqual(str(caught.exception),case['expected']['reason'])

    def test_rollback(self):
        case=selected('late-test-rollback')
        self.assertEqual(analyze(case['input'])[0]['result'],{'q':2})

    def test_post_removal_destination(self):
        self.assertEqual(analyze(selected('move-forward')['input'])[0]['result'],[8,10,11,9])

    def test_typed_equality(self):
        self.assertEqual(analyze(selected('test-false-zero')['input'])[1],4)

    def test_copy_detaches_working_subtree(self):
        source={'q':[8]};operation={'op':'copy','from':'/q','path':'/r'}
        spec=validate(env(source,[operation]))[0]
        result=_apply(_clone(source),operation,spec)
        result['q'].append(9)
        self.assertEqual(result['r'],[8])

    def test_decoded_ancestry(self):
        self.assertEqual(analyze(selected('string-prefix-not-ancestry')['input'])[1],1)

    def test_missing_parent(self):
        self.assertEqual(analyze(selected('no-parent-creation')['input'])[1],4)

    def test_node_growth(self):
        self.assertEqual(analyze(selected('fifth-copy-node-limit')['input'])[1],4)

    def test_output_amplification(self):
        case=FROZEN['overflow_uncapped']
        source=parse(FROZEN['errors'][-1]['raw'].encode('utf-8'))
        report,code=analyze(source)
        # Report equality is tested separately; this assertion detects real delivery cap.
        self.assertEqual((report,code),(case['expected'],0))
        with self.assertRaisesRegex(LabError,'^resource limit$'):render(report)

    def test_output_cap_only(self):
        report,_=analyze(parse(FROZEN['errors'][-1]['raw'].encode('utf-8')))
        with self.assertRaisesRegex(LabError,'^resource limit$'):render(report)

    def test_detached_report_and_logical_aliases(self):
        shared=[{'q':8}];source=env({'a':shared,'b':shared},[{'op':'copy','from':'/a','path':'/c'}])
        report,_=analyze(source)
        report['result']['a'][0]['q']=9
        self.assertEqual(report['result']['b'][0]['q'],8)
        self.assertEqual(report['result']['c'][0]['q'],8)
        self.assertEqual(report['target']['a'][0]['q'],8)
        report['operations'][0]['path']='/different'
        self.assertEqual(source['operations'][0]['path'],'/c')
        self.assertEqual(shared,[{'q':8}])

    def test_native_no_hooks(self):
        calls=[]
        class Meta(type):
            def __eq__(self,other):calls.append('eq');raise RuntimeError('hook')
        class Foreign(metaclass=Meta):pass
        class Mapping(dict):
            def items(self):calls.append('items');raise RuntimeError('hook')
            def __deepcopy__(self,memo):calls.append('copy');raise RuntimeError('hook')
        class Text(str):
            def __hash__(self):calls.append('hash');return super().__hash__()
        keyed={Text('q'):8};calls.clear()
        for value in (Foreign(),Mapping(q=8),keyed,{'q':Foreign()},(1,),1.0):
            with self.assertRaises(LabError):analyze(env(value))
        self.assertEqual(calls,[])

    def test_cycles_and_late_ignored_branches(self):
        cycle=[];cycle.append(cycle)
        for source in (env(cycle),env(None,[{'op':'test','path':'','value':None,'extra':cycle}])):
            with self.assertRaises(LabError):analyze(source)
        envelope=env();envelope['target']=envelope
        with self.assertRaises(LabError):analyze(envelope)
        with self.assertRaises(LabError):analyze(env({},[{'op':'remove','path':'/q'},{'op':'test','path':'','value':{},'extra':object()}],schema='future'))

    def test_lexical_gates_before_decoder(self):
        for raw in (b'['*11+b']'*11,b'9'*33,b'1e5',b'-0',b'9007199254740992'):
            with patch.object(contract.json,'loads',side_effect=RuntimeError('decoder called')):
                with self.assertRaises(LabError):parse(raw)

    def test_encoding_duplicate_and_unicode(self):
        for raw in (b'\xef\xbb\xbf{}',b'\xff',b'{} {}',b'{"q":1,"\\u0071":2}'):
            with self.assertRaises(LabError):parse(raw)
        for text in ('\ud800','\ufdd0','\U0010ffff'):
            with self.assertRaises(LabError):analyze(env(text))
        for text in ('','\x00','\u200d','\ue000','\u0378'):
            self.assertEqual(analyze(env(text))[0]['result'],text)

    def test_raw_bound(self):
        raw=json.dumps(env()).encode()
        self.assertEqual(parse(raw+b' '*(65536-len(raw))),env())
        with self.assertRaisesRegex(LabError,'resource limit'):parse(raw+b' '*(65537-len(raw)))

    def test_native_tree_and_pointer_bounds(self):
        self.assertEqual(analyze(env([0]*511))[1],0)
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env([0]*512))
        tree=0
        for _ in range(7):tree=[tree]
        self.assertEqual(analyze(env(tree))[1],0)
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env([tree]))
        self.assertEqual(analyze(env('x'*128))[1],0)
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env('x'*129))
        for path in ('/'+'x'*129,'/'*9,'/'+'x'*512):
            with self.assertRaisesRegex(LabError,'resource limit'):analyze(env({},[{'op':'remove','path':path}]))
        self.assertEqual(analyze(env(None,[{'op':'test','path':'','value':None}]*16))[1],0)
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env(None,[{'op':'test','path':'','value':None}]*17))

    def test_containers_text_and_logical_counts(self):
        self.assertEqual(analyze(env([[] for _ in range(63)]))[1],0)
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env([[] for _ in range(64)]))
        self.assertEqual(analyze(env(['x'*128]*16))[1],0)
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env(['x'*128]*16+['x']))
        shared=[0]*300
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env([shared,shared]))

    def test_operation_and_global_budgets(self):
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env(None,[{'op':'test','path':'','value':None,'extra':[0]*510}]))
        with self.assertRaisesRegex(LabError,'resource limit'):analyze(env(None,[{'op':'test','path':'','value':None,'extra':['x'*128]*16}]))
        operation={'op':'test','path':'','value':None,'extra':[0]*251}
        # Individual operations admit; enough repetitions exhaust the whole tree.
        validate(env(None,[operation]*15))
        with self.assertRaisesRegex(LabError,'resource limit'):validate(env(None,[operation]*16))
        operation={'op':'test','path':'','value':None,'extra':['x'*128]*15}
        validate(env(None,[operation]*8))
        with self.assertRaisesRegex(LabError,'resource limit'):validate(env(None,[operation]*9))

    def test_working_depth_and_text_rejection(self):
        value=0
        for _ in range(7):value=[value]
        report,code=analyze(env({},[{'op':'add','path':'/q','value':value}]))
        self.assertEqual((code,report['failure_index'],report['trace'][0]['reason'],report['result']),(4,0,'resource-limit',{}))
        initial={str(i):'x'*120 for i in range(16)}
        operations=[{'op':'copy','from':'','path':'/snapshot'},{'op':'copy','from':'','path':'/snapshot2'}]
        report,code=analyze(env(initial,operations))
        self.assertEqual((code,report['failure_index'],report['result']),(4,1,initial))

    def test_working_container_rejection(self):
        initial=[[] for _ in range(63)]
        report,code=analyze(env(initial,[{'op':'copy','from':'','path':'/-'}]*2))
        self.assertEqual((code,report['failure_index'],report['result']),(4,1,initial))

    def test_integer_and_context_indices(self):
        for value in (9007199254740991,-9007199254740991):self.assertEqual(analyze(env(value))[1],0)
        for value in (9007199254740992,-9007199254740992):
            with self.assertRaises(LabError):analyze(env(value))
        for token in ('+0','-1',' 0','\u0660','1'*128,'-'):
            report,code=analyze(env([8],[{'op':'test','path':'/'+token,'value':8}]))
            self.assertEqual(code,4)
        self.assertEqual(analyze(env({'-':8},[{'op':'test','path':'/-','value':8}]))[1],0)


if __name__=='__main__':unittest.main()
