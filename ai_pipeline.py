"""Automated, blind, image-by-image discovery and held-out validation."""
import base64, hashlib, io, json, os, time, threading
from pathlib import Path
from PIL import Image, ImageDraw
from openai import OpenAI

MODEL = 'gpt-4.1-mini'
# Deliberately conservative per-million-token estimates; adjust if model pricing changes.
IN_RATE, OUT_RATE = 3.0, 12.0
LIMIT = 4.0  # USD app-side stop, below the user's total $5 prepaid credit
RESERVE_PER_CALL = 0.18  # Temporary in-flight reservation, not permanent expenditure
LOCK = threading.RLock()
LEDGER = Path('data/ai_budget_v4.json')
LEGACY = Path('data/ai_budget_v3.json')

def ledger():
    with LOCK:
        try:
            return json.loads(LEDGER.read_text())
        except (OSError, ValueError):
            try:
                old=json.loads(LEGACY.read_text())
                # Carry forward only actual estimated token costs, not unused reservations.
                return {'estimated_usd':float(old.get('estimated_usd',0)),
                        'calls':int(old.get('calls',0)), 'in_flight_usd':0.,
                        'legacy_reserved_usd':float(old.get('reserved_usd',0))}
            except (OSError, ValueError):
                return {'estimated_usd':0.,'calls':0,'in_flight_usd':0.}

def save_ledger(d):
    LEDGER.parent.mkdir(exist_ok=True)
    tmp=LEDGER.with_suffix('.tmp')
    tmp.write_text(json.dumps(d,indent=2))
    os.replace(tmp,LEDGER)

def reserve():
    with LOCK:
        d=ledger()
        if d['estimated_usd']+d.get('in_flight_usd',0)+RESERVE_PER_CALL > LIMIT:
            raise RuntimeError('Internal budget guard reached; no API request sent.')
        d['in_flight_usd']=d.get('in_flight_usd',0)+RESERVE_PER_CALL
        save_ledger(d)

def settle(estimate=None):
    with LOCK:
        d=ledger()
        d['in_flight_usd']=max(0.,d.get('in_flight_usd',0)-RESERVE_PER_CALL)
        # When an API call fails, charge the full reservation as a precaution.
        d['estimated_usd']+=RESERVE_PER_CALL if estimate is None else max(0.,estimate)
        d['calls']+=1
        save_ledger(d)

def jpeg_data(raw):
    im=Image.open(io.BytesIO(raw)).convert('RGB');im.thumbnail((1200,1200))
    buf=io.BytesIO();im.save(buf,format='JPEG',quality=82)
    return 'data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()

def ask(key, prompt, photos, max_tokens=1100):
    reserve()
    client=OpenAI(api_key=key,timeout=130,max_retries=0)
    content=[{'type':'text','text':prompt}]
    for label,raw in photos:
        content.extend([{'type':'text','text':f'Photo ID: {label}'},{'type':'image_url','image_url':{'url':jpeg_data(raw),'detail':'high'}}])
    try:
        result=client.chat.completions.create(model=MODEL,temperature=0,max_tokens=max_tokens,response_format={'type':'json_object'},messages=[{'role':'user','content':content}])
        u=result.usage
        settle((u.prompt_tokens*IN_RATE+u.completion_tokens*OUT_RATE)/1e6)
        return json.loads(result.choices[0].message.content)
    except Exception:
        # Do not charge twice when parsing fails after successful settlement.
        if 'result' not in locals(): settle(None)
        raise

TRAITS='''Use ONLY observable moth anatomy and markings; do not use field guides, memorized species diagnoses, or background. Each trait must refer to a precise visible wing region. Ignore lighting and general hue unless reliably intrinsic. If not visible say unknown. Return JSON only.'''

def inspect_batch(key, images):
    ids=[x[0] for x in images]
    prompt=TRAITS+''' Examine each photograph independently. Return {"photos":[{"id":"exact supplied ID","usable":true/false,"traits":[{"region":"specific region","state":"short concrete appearance"}]}]}. Maximum four traits per photo; never infer traits not visible. Include each ID exactly once. IDs: '''+', '.join(ids)
    return ask(key,prompt,images,max_tokens=1400).get('photos',[])

def propose(key, per_species):
    prompt=TRAITS+''' These are observations of independent photos, already recorded without reference to other species. Identify up to 3 candidate morphological traits that might separate the two labeled groups. Avoid generic color differences. Provide an operational yes/no question for each candidate that can be answered on a new photograph without knowing its species. Return {"candidates":[{"name":"short name","region":"exact anatomical region","question":"Is ...? (yes/no/unknown)","positive_species":"exact species label","rationale":"..."}]}. No unsupported certainty. Data: '''+json.dumps(per_species,ensure_ascii=False)
    return ask(key,prompt,[],max_tokens=1200).get('candidates',[])

def verify_batch(key, candidate, images):
    prompt=TRAITS+''' Independently answer ONLY this predefined binary question for every photo: '''+candidate['question']+''' Return {"photos":[{"id":"exact ID","answer":"yes|no|unknown","reason":"visible observation, max 15 words"}]}. Unknown if angle or wear prevents checking. Do not use species names. IDs: '''+', '.join(x[0] for x in images)
    return ask(key,prompt,images,max_tokens=900).get('photos',[])

def locate(key, candidate, photo):
    prompt=TRAITS+''' For the supplied image, locate the visible feature for annotation. Return {"visible":true/false,"x_pct":number or null,"y_pct":number or null,"label":"short visible feature label"}. Coordinates are relative to entire image 0-100; only mark if genuinely visible. Feature: '''+candidate['name']+'; '+candidate['question']
    return ask(key,prompt,[photo],max_tokens=220)

def draw(raw,species,markers,attribution):
    im=Image.open(io.BytesIO(raw)).convert('RGB');im.thumbnail((1100,850))
    card=Image.new('RGB',(max(im.width,950),im.height+95+65*len(markers)),'white')
    left=(card.width-im.width)//2;card.paste(im,(left,0));d=ImageDraw.Draw(card)
    d.text((16,im.height+14),species+' — EXPERIMENTAL / NOT VERIFIED',fill='black')
    for i,m in enumerate(markers):
        x=left+int(im.width*m['x_pct']/100);y=int(im.height*m['y_pct']/100)
        d.ellipse((x-12,y-12,x+12,y+12),outline='#e11d48',width=4)
        d.line((x+12,y-12,x+34,y-32),fill='#e11d48',width=3)
        d.text((18,im.height+45+65*i),f'{i+1}. {m["label"][:100]}',fill='#a61b35')
    d.text((18,card.height-22),('Photo: '+attribution)[:125],fill='#555555')
    out=io.BytesIO();card.save(out,'PNG');return out.getvalue()

def run(key, records, get_image, progress):
    names=list(records)
    if len(names)!=2: raise ValueError('Exactly two species required')
    # Fixed split before any AI work: 12 discovery + 8 validation per species.
    sample={name:records[name][:20] for name in names}
    if any(len(x)<16 for x in sample.values()): raise ValueError('At least 16 photos per species required')
    prepared={}
    for name in names:
        prepared[name]=[]
        for i,item in enumerate(sample[name]):
            try:prepared[name].append((f'{names.index(name)}-{i+1}',get_image(item['url']),item))
            except Exception:continue
    if any(len(v)<16 for v in prepared.values()):raise ValueError('Not enough downloadable photos')
    # 8 discovery, 8 holdout, to fit conservative budget; independently chosen per observer upstream.
    discovery={n:prepared[n][:8] for n in names};holdout={n:prepared[n][8:16] for n in names}
    observations={}
    for name in names:
        observations[name]=[]
        for i in (0,4):
            progress('Examining individual photos: '+name)
            observations[name].extend(inspect_batch(key,[(p[0],p[1]) for p in discovery[name][i:i+4]]))
    progress('Generating candidate differences from observations')
    candidates=propose(key,observations)[:3]
    verified=[]
    for c in candidates:
        if c.get('positive_species') not in names or not c.get('question'):continue
        tally={};examples={}
        for name in names:
            ans=[]
            for i in (0,4):
                progress('Testing held-out photographs: '+name)
                ans+=verify_batch(key,c,[(p[0],p[1]) for p in holdout[name][i:i+4]])
            by_id={a.get('id'):a.get('answer') for a in ans}
            tally[name]={k:sum(by_id.get(p[0])==k for p in holdout[name]) for k in ('yes','no','unknown')}
            examples[name]=[p for p in holdout[name] if by_id.get(p[0])=='yes']
        pos=c['positive_species'];neg=next(n for n in names if n!=pos)
        a=tally[pos];b=tally[neg]
        na=a['yes']+a['no'];nb=b['yes']+b['no']
        # Conservative rule: high prevalence, separation, enough evaluable images.
        accepted=(na>=6 and nb>=6 and a['yes']/na>=.75 and b['yes']/nb<=.25 and (a['yes']/na-b['yes']/nb)>=.5)
        c.update({'counts':tally,'accepted':accepted,'reason':'held-out prevalence criterion' if accepted else 'insufficient repeatable separation'})
        if accepted and examples[pos]:
            photo=examples[pos][0]
            progress('Locating feature on representative image')
            loc=locate(key,c,(photo[0],photo[1]))
            if loc.get('visible') and all(isinstance(loc.get(k),(int,float)) and 0<=loc[k]<=100 for k in ('x_pct','y_pct')):
                c['card']={'species':pos,'photo_id':photo[0],'photo':photo[2], 'location':loc}
        verified.append(c)
    return {'species':names,'model':MODEL,'discovery_photos_per_species':8,'holdout_photos_per_species':8,'candidates':verified,'observations':observations}
