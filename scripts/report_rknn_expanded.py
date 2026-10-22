"""Summarize structured expanded-trial evidence, including a blocked INT8 stage."""
import json
from pathlib import Path
from focuslens.deployment.evaluation import edits


def report(root):
    protocol = json.loads((root / 'inputs.json').read_text())
    records = json.loads((root / 'parity.json').read_text())['records']
    result = dict(counts={key: len(protocol[key]) for key in ('calibration','parity')},
                  groups={key: len({r['group'] for r in protocol[key]}) for key in ('calibration','parity')},
                  available_groups=protocol['available_groups'], rejected=protocol['rejected'],
                  overlap={key: len({r[key] for r in protocol['calibration']} &
                                    {r[key] for r in protocol['parity']}) for key in ('sha256','group')},
                  fp32_numeric_pass=sum(r['numeric_pass'] for r in records),
                  fp32_max_abs=max(r['max_abs'] for r in records),
                  failed=[{k:r[k] for k in ('id','max_abs','mean_abs','paddle','onnx')}
                          for r in records if not r['numeric_pass']], metrics={})
    for key in ('dynamic_paddle','paddle','onnx'):
        distances=[edits(r['reference'],r[key][0][0]) for r in records]
        result['metrics'][key]=dict(exact=sum(d==0 for d in distances), edits=sum(distances),
            characters=sum(len(r['reference']) for r in records),
            cer=sum(distances)/sum(len(r['reference']) for r in records))
    result['coverage']={tag: {str(value):sum(r['tags'][tag] == value for r in protocol['parity'])
                            for value in {r['tags'][tag] for r in protocol['parity']}}
                        for tag in protocol['parity'][0]['tags']}
    result['infeasible_ctc']=sum(r['minimum_ctc_steps']>40 for r in protocol['parity'])
    result['fixed_vs_dynamic']=dict(degrade=sum(edits(r['reference'],r['paddle'][0][0]) > edits(r['reference'],r['dynamic_paddle'][0][0]) for r in records),
        rescue=sum(edits(r['reference'],r['paddle'][0][0]) < edits(r['reference'],r['dynamic_paddle'][0][0]) for r in records))
    result['status']=json.loads((root / 'status.json').read_text())
    (root/'expanded-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    report(Path('.cache/rknn-export/expanded-v1'))
