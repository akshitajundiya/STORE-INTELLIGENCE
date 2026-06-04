import json, urllib.request

lines = [json.loads(l) for l in open('data/events.jsonl')]
batch_size = 100
total_accepted = 0

for i in range(0, len(lines), batch_size):
    batch = lines[i:i+batch_size]
    body = json.dumps({'events': batch}).encode()
    req = urllib.request.Request('http://localhost:8000/events/ingest', data=body, headers={'Content-Type': 'application/json'}, method='POST')
    resp = urllib.request.urlopen(req)
    r = json.loads(resp.read())
    total_accepted += r['accepted']
    print('Batch', i//batch_size+1, 'accepted=', r['accepted'], 'dup=', r['duplicates'], 'rej=', r['rejected'])

print('Total accepted:', total_accepted)
