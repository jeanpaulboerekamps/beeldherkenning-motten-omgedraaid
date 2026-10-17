"""Experimental image-based feature discovery; no literature lookup."""
import base64
import hashlib
import io
import json
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

# Conservative internal accounting estimates in USD, not official model prices.
INPUT_PER_M = 1.0
OUTPUT_PER_M = 6.0
MODEL = 'gpt-4.1-mini'

def compact_image(raw):
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    im.thumbnail((640,640))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=76)
    return base64.b64encode(b.getvalue()).decode()

def contact_sheet(items, get_image, species, max_items=20):
    """Labeled 4x5 grid. IDs map back to original photographs."""
    chosen = items[:max_items]
    w,h = 300,260
    sheet = Image.new('RGB',(w*4,h*5),'white')
    d=ImageDraw.Draw(sheet)
    used=[]
    for i,item in enumerate(chosen):
        try:
            im=Image.open(io.BytesIO(get_image(item['url']))).convert('RGB')
            im.thumbnail((w-12,h-34))
            x=(i%4)*w+(w-im.width)//2; y=(i//4)*h+27
            sheet.paste(im,(x,y));d.text(((i%4)*w+8,(i//4)*h+6),f'{species} #{i+1}',fill='black')
            used.append({'index':i+1,**item})
        except Exception: pass
    if not used: raise ValueError('No photographs could be loaded')
    out=io.BytesIO();sheet.save(out,'JPEG',quality=78)
    return out.getvalue(),used

def call_vision(key, sheet_a, sheet_b, species_a, species_b):
    prompt=f'''This is a BLIND comparative visual experiment on two labeled moth photo grids: A={species_a}, B={species_b}. Do not use field-guide facts or literature. Look at recurring VISUALLY OBSERVABLE differences across specimens, not background, lighting, size, wear, camera angle or single odd examples. Be skeptical. Return JSON only, with fields: "summary" (string), "features" (array of 0 to 3 objects), "limitations" (string). Each feature: "species" (one of the two names), "description" (brief English), "contrast" (brief explanation compared with other species), "supporting_photo_numbers" (array of numbers 1-20 for that species), "exceptions" (string), "confidence" (one of low, moderate), "x_pct" and "y_pct" (integer 0-100; approximate location of trait in FIRST supporting photo; if uncertain set both null). Do not claim confirmed diagnostic traits. Return zero features if no repeatable differences are visible. Photos in grids are separate individuals; do not assume labels guarantee correct IDs.'''
    client=OpenAI(api_key=key, timeout=120, max_retries=0)
    resp=client.chat.completions.create(model=MODEL,temperature=0,max_tokens=1000,response_format={'type':'json_object'},messages=[{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(sheet_a).decode(),'detail':'low'}},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(sheet_b).decode(),'detail':'low'}}]}])
    data=json.loads(resp.choices[0].message.content)
    usage=resp.usage
    tokens_in=int(usage.prompt_tokens or 0);tokens_out=int(usage.completion_tokens or 0)
    estimate=(tokens_in*INPUT_PER_M+tokens_out*OUTPUT_PER_M)/1_000_000
    return data, {'input_tokens':tokens_in,'output_tokens':tokens_out,'estimated_usd':estimate,'model':MODEL}

def render_card(raw,species,features,photo_index,attribution):
    im=Image.open(io.BytesIO(raw)).convert('RGB'); im.thumbnail((1100,850))
    features=[f for f in features if photo_index in f.get('supporting_photo_numbers',[])][:3]
    card=Image.new('RGB',(max(900,im.width),im.height+170+len(features)*75),'white')
    card.paste(im,((card.width-im.width)//2,20))
    d=ImageDraw.Draw(card)
    for i,f in enumerate(features):
        x,y=f.get('x_pct'),f.get('y_pct')
        if isinstance(x,(float,int)) and isinstance(y,(float,int)):
            cx=(card.width-im.width)//2+int(im.width*x/100);cy=20+int(im.height*y/100)
            d.ellipse((cx-14,cy-14,cx+14,cy+14),outline='#dc2626',width=4)
            d.line((cx+14,cy-14,cx+38,cy-35),fill='#dc2626',width=3)
            d.text((cx+40,cy-42),str(i+1),fill='#dc2626',stroke_width=2,stroke_fill='white')
    base=im.height+36
    d.text((20,base),species+' — EXPERIMENTAL / UNVALIDATED',fill='black')
    for i,f in enumerate(features):
        desc=str(f.get('description',''))[:115]
        d.text((20,base+36+i*75),f'{i+1}. {desc}',fill='#a31b1b')
        d.text((20,base+57+i*75),'Confidence: '+str(f.get('confidence','low')),fill='#555555')
    d.text((20,card.height-28),('Photo: '+attribution)[:130],fill='#555555')
    out=io.BytesIO();card.save(out,'PNG');return out.getvalue()
