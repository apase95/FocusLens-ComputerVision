"""Case-sensitive, punctuation-preserving character metrics; no label tuning."""
def edits(reference, text):
    previous = list(range(len(text)+1))
    for i, a in enumerate(reference, 1):
        current = [i]
        for j, b in enumerate(text, 1):
            current.append(min(current[-1]+1, previous[j]+1, previous[j-1]+(a != b)))
        previous = current
    return previous[-1]


def summarize(root):
    import json
    protocol = json.loads((root / 'inputs.json').read_text())
    fp = json.loads((root / 'parity.json').read_text())['records']
    quant = json.loads((root / 'simulator-parity.json').read_text())['records']
    if len(fp) != len(protocol['parity']) or len(quant) != len(fp):
        raise ValueError('Incomplete inference records')
    rows = []
    for source, fixed, integer in zip(protocol['parity'], fp, quant):
        row = dict(source, predictions={}, error=None, max_abs_int8=integer['max_abs'],
                   mean_abs_int8=integer['mean_abs'], numeric_pass_int8=integer['numeric_pass'],
                   argmax_changed_steps=integer['argmax_changed_steps'],
                   ctc_feasible=source['minimum_ctc_steps'] <= 40)
        for key, decoded in [('dynamic', fixed['dynamic_paddle']), ('fixed', fixed['paddle']),
                             ('onnx', fixed['onnx']), ('int8', integer['simulator'])]:
            text, score = decoded[0]
            distance = edits(source['reference'], text)
            row['predictions'][key] = dict(text=text, confidence_uncalibrated=score,
                edits=distance, exact=text == source['reference'],
                cer=distance/max(1, len(source['reference'])),
                casefold_edits=edits(source['reference'].casefold(), text.casefold()),
                casefold_exact=source['reference'].casefold() == text.casefold(),
                severe_content_loss=len(text) < len(source['reference'])/2)
        rows.append(row)
    def aggregate(items):
        result = dict(count=len(items), characters=sum(len(r['reference']) for r in items))
        for key in ('dynamic', 'fixed', 'onnx', 'int8'):
            result[key] = dict(exact=sum(r['predictions'][key]['exact'] for r in items),
                edits=sum(r['predictions'][key]['edits'] for r in items),
                severe_content_loss=sum(r['predictions'][key]['severe_content_loss'] for r in items))
            result[key]['cer'] = result[key]['edits']/max(1,result['characters'])
            result[key]['casefold_secondary'] = dict(
                exact=sum(r['predictions'][key]['casefold_exact'] for r in items),
                edits=sum(r['predictions'][key]['casefold_edits'] for r in items),
                characters=sum(len(r['reference'].casefold()) for r in items))
            folded = result[key]['casefold_secondary']
            folded['cer'] = folded['edits']/max(1, folded['characters'])
        for a,b in [('dynamic','fixed'), ('fixed','int8')]:
            result[a+'->'+b] = dict(
                degrade=sum(r['predictions'][b]['edits'] > r['predictions'][a]['edits'] for r in items),
                rescue=sum(r['predictions'][b]['edits'] < r['predictions'][a]['edits'] for r in items),
                 string_changed=sum(r['predictions'][b]['text'] != r['predictions'][a]['text'] for r in items))
            result[a+'->'+b]['casefold_secondary'] = dict(
                degrade=sum(r['predictions'][b]['casefold_edits'] > r['predictions'][a]['casefold_edits'] for r in items),
                rescue=sum(r['predictions'][b]['casefold_edits'] < r['predictions'][a]['casefold_edits'] for r in items))
        return result
    summary = dict(overall=aggregate(rows), infeasible_ctc=sum(not r['ctc_feasible'] for r in rows),
                    exceptions=0, strata={}, primary='case-sensitive; punctuation preserved',
                    secondary='Unicode casefold; not primary acceptance',
                    regressions={})
    for a, b in [('dynamic', 'fixed'), ('fixed', 'int8')]:
        summary['regressions'][a+'->'+b] = [dict(id=r['id'], reference=r['reference'],
            before=r['predictions'][a], after=r['predictions'][b]) for r in rows
            if r['predictions'][b]['edits'] > r['predictions'][a]['edits']]
    for tag in ('wide','repeated','digits','punctuation','lowheight','lowcontrast','case','length'):
        for value in sorted({str(r['tags'][tag]) for r in rows}):
            summary['strata'][f'{tag}={value}'] = aggregate([r for r in rows if str(r['tags'][tag]) == value])
    for name, value in [('evaluation-rows.json',rows),('evaluation-summary.json',summary)]:
        (root/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    return summary
