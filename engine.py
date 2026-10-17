"""Photo-only descriptive feature discovery. No identification claims."""
import base64, io, json, os, threading
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

MODEL='gpt-4.1-mini'
LIMIT_USD=3.75  # internal safety stop, NOT a billing cap
RESERVE=0.15
RATE_IN=3.0/1e6; RATE_OUT=12.0/1e6  # deliberately conservative estimates; not authoritative prices
PATH=Path('data/v5_budget.json')
LOCK=threading.RLock()

def ledger():
    try:return json.loads(PATH.read_text())
    except Exception:return {'spent_estimate':0.,'pending':0.,'calls':0}

def _save(d):
    PATH.parent.mkdir(parents=True,exist_ok=True)
    tmp=PATH.with_suffix('.tmp');tmp.write_text(json.dumps(d));os.replace(tmp,PATH)

def reserve():
    with LOCK:
        d=ledger()
        if d['spent_estimate']+d['pending']+RESERVE>LIMIT_USD:
            raise RuntimeError('Local budget guard reached. Check actual OpenAI balance; do not reset guard to bypass it.')
        d['pending']+=RESERVE;_save(d)

def settle(cost=None):
    with LOCK:
        d=ledger();d['pending']=max(0,d['pending']-RESERVE)
        d['spent_estimate']+=RESERVE if cost is None else max(0,cost)
        d['calls']+=1;_save(d)

def jpeg(raw):
    im=Image.open(io.BytesIO(raw)).convert('RGB');im.thumbnail((1100,1100))
    buf=io.BytesIO();im.save(buf,'JPEG',quality=84)
    return 'data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()

def ask(key, instructions, photos=(), max_tokens=1300):
    reserve();completed=False
    try:
        content=[{'type':'text','text':instructions}]
        for pid,raw in photos:
            content.append({'type':'text','text':'Image '+str(pid)})
            content.append({'type':'image_url','image_url':{'url':jpeg(raw),'detail':'high'}})
        r=OpenAI(api_key=key,timeout=120,max_retries=0).chat.completions.create(
            model=MODEL,temperature=0,max_tokens=max_tokens,response_format={'type':'json_object'},
            messages=[{'role':'user','content':content}])
        u=r.usage;settle(u.prompt_tokens*RATE_IN+u.completion_tokens*RATE_OUT);completed=True
        return json.loads(r.choices[0].message.content)
    except Exception:
        if not completed:settle(None)
        raise

BASE='''You are a visual morphology recorder. Do not identify the animal. Do not use species names, field guides, known species traits, or infer hidden structures. Only record directly visible shapes, marks and positions in the supplied image. Avoid generic moth anatomy. If uncertain, say uncertain. Do not invent coordinates. JSON only. '''

def describe(key,pid,raw):
    prompt=BASE+'''Examine ONE image. Return {"usable":boolean,"reason":"short","features":[{"region":"precise visible location","appearance":"concrete visible shape/mark","point":[x,y],"confidence":0.0}]}.
Up to 6 distinct visible features. Point is the location on the image, in normalized 0..1000 coordinates from top-left; never point to a hidden structure. Include only observable features, not taxonomic guesses. Ignore backgrounds. If moth is tiny, obstructed, or indistinct set usable=false. '''
    d=ask(key,prompt,[(pid,raw)],1050)
    d['id']=pid
    return d

def summarize(key,descriptions):
    compact=[{'id':d['id'],'usable':d.get('usable'),'features':[{'region':f.get('region'),'appearance':f.get('appearance')} for f in d.get('features',[])]} for d in descriptions]
    prompt=BASE+'''These are independent descriptions of images of the SAME unidentified kind of animal. Cluster only genuinely matching visible features (similar region AND appearance); do not merge generic features. Return {"candidates":[{"name":"short descriptive label","description":"observable appearance and exact location","supporting_ids":["ids present in input"],"check_question":"Does the visible photo show ...?"}]} with at most 5 candidates. supporting_ids MUST be IDs whose individual description actually reports the trait. No species knowledge. Data: '''+json.dumps(compact)
    return ask(key,prompt,[],1800).get('candidates',[])

def check(key,candidate,pid,raw):
    prompt=BASE+'''Independently check this proposed feature in ONE photo. Do not assume it is present. Return {"state":"yes|no|unknown","point":[x,y] or null,"reason":"short"}. Answer unknown when feature's anatomical region is hidden or photo inadequate. Coordinates normalized 0..1000, on the feature itself, only if yes. Feature: '''+json.dumps({'description':candidate.get('description'),'question':candidate.get('check_question')})
    d=ask(key,prompt,[(pid,raw)],260)
    d['id']=pid
    return d

def valid_point(p):
    return isinstance(p,list) and len(p)==2 and all(isinstance(x,(int,float)) and 0<=x<=1000 for x in p)

def annotate(raw, features):
    im=Image.open(io.BytesIO(raw)).convert('RGB');im.thumbnail((1250,1050))
    w,h=im.size;canvas=Image.new('RGB',(w+420,h),(250,250,248));canvas.paste(im,(0,0));d=ImageDraw.Draw(canvas)
    try:font=ImageFont.truetype('DejaVuSans.ttf',19)
    except Exception:font=ImageFont.load_default()
    for i,f in enumerate(features[:3]):
        p=f.get('point')
        if not valid_point(p):continue
        x=int(p[0]*w/1000);y=int(p[1]*h/1000)
        tx=w+20;ty=45+i*int(max(100,(h-70)/3))
        d.line([(x,y),(w+8,ty+7)],fill=(205,45,40),width=3)
        d.ellipse((x-8,y-8,x+8,y+8),outline=(205,45,40),width=3)
        label=str(f.get('name','feature'))[:40]
        desc=str(f.get('description',''))[:95]
        d.text((tx,ty),label,fill=(20,20,20),font=font)
        d.text((tx,ty+27),desc[:43],fill=(60,60,60),font=font)
        d.text((tx,ty+51),desc[43:86],fill=(60,60,60),font=font)
    b=io.BytesIO();canvas.save(b,'PNG');return b.getvalue()
