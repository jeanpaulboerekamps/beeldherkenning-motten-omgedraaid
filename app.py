import io
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from ai_pipeline import run as run_pipeline, ledger, draw, LIMIT, RESERVE_PER_CALL

st.set_page_config(page_title='Moth comparison lab', layout='wide')
st.title('🦋 Moth comparison lab')
st.caption('Blind photo comparison • iNaturalist research-grade observations • experimental feature discovery')
API = 'https://api.inaturalist.org/v1/observations'
CACHE = Path('data'); CACHE.mkdir(exist_ok=True)
DEFAULT = ['Noctua comes', 'Noctua interjecta']

@st.cache_data(ttl=86400, show_spinner=False)
def observations(name, n):
    r = requests.get(API, params={'taxon_name':name, 'quality_grade':'research','photos':'true','per_page':min(200,max(n*3,40)),'order_by':'observed_on','order':'desc'}, timeout=35, headers={'User-Agent':'MothComparisonLab/0.1 (research demo)'})
    r.raise_for_status()
    result=[]; seen=set()
    for ob in r.json().get('results',[]):
        if (ob.get('taxon') or {}).get('name','').lower()!=name.lower():continue
        if ob.get('user',{}).get('login') in seen:continue
        photos=ob.get('photos') or []
        if not photos:continue
        p=photos[0]; url=(p.get('url') or '').replace('square.','medium.')
        if not url:continue
        seen.add(ob.get('user',{}).get('login'))
        result.append({'id':ob['id'],'species':name,'url':url,'observer':ob.get('user',{}).get('login',''),'attribution':p.get('attribution') or '', 'license':p.get('license_code') or 'unknown','link':f"https://www.inaturalist.org/observations/{ob['id']}"})
        if len(result)>=n:break
    return result

@st.cache_data(ttl=86400, show_spinner=False)
def get_image(url):
    r=requests.get(url,timeout=20,headers={'User-Agent':'MothComparisonLab/0.1'})
    r.raise_for_status()
    return r.content

def rgb_features(data):
    im=Image.open(io.BytesIO(data)).convert('RGB')
    w,h=im.size
    # Central image statistics are exploratory only; backgrounds, lighting and posture confound results.
    a=np.asarray(im.resize((128,128)),dtype=np.float32)
    center=a[24:104,24:104,:]
    mean=center.mean(axis=(0,1))
    gray=center.mean(axis=2)
    return {'brightness':float(gray.mean()),'contrast':float(gray.std()),'redness':float(mean[0]-mean[2]),'warmth':float(mean[0]-mean[1])}

def report(records):
    lines=['# Blind comparison report','', 'Automated image statistics are NOT diagnostic anatomical characters. Backgrounds and lighting can dominate these signals.','']
    for name, items in records.items():
        lines.extend([f'## {name}',f'Photos: {len(items)}',''])
        feats=[]
        for item in items:
            try:feats.append(rgb_features(get_image(item['url'])))
            except Exception:pass
        for k in ('brightness','contrast','redness','warmth'):
            if feats:lines.append(f'- {k}: mean {np.mean([f[k] for f in feats]):.1f}; SD {np.std([f[k] for f in feats]):.1f}')
        lines.append('')
    lines.extend(['## Human visual inspection','Describe recurring wing shape, spots, cross-lines and posture separately for each species, then verify across multiple photos.','', '## Validation','Only after recording hypotheses, consult identification literature. Do not interpret these image statistics as proven species characters.'])
    return '\n'.join(lines)

with st.sidebar:
    st.header('Sample')
    species_a=st.text_input('Species A',DEFAULT[0])
    species_b=st.text_input('Species B',DEFAULT[1])
    n=st.slider('Observations per species',5,100,20,5)
    st.caption('One photograph per observer where possible. Photos are fetched only when needed and cached for 24 hours.')
    load=st.button('Fetch photographs',type='primary',use_container_width=True)
if load:
    try:
        with st.spinner('Fetching iNaturalist observations…'):
            st.session_state['records']={species_a:observations(species_a,n),species_b:observations(species_b,n)}
    except Exception as e:st.error(f'Unable to retrieve photographs: {e}')
records=st.session_state.get('records')
if not records:
    st.info('Choose two species and select **Fetch photographs** to start. No photographs are bundled with this application.')
    st.stop()

for name,items in records.items():
    st.write(f'**{name}: {len(items)} photographs**')
    if len(items)<5:st.warning('Small sample: results may not be representative.')

tab0,tab1,tab2,tab3=st.tabs(['Automatic AI discovery','Photo comparison','Blind notes & statistics','Manual card (legacy)'])
with tab0:
    st.subheader('Fully automatic feature discovery — v4')
    st.caption('Individual images → candidate traits → independent held-out test → automatic annotated cards. No human review or field-guide text.')
    st.warning('The €5 goal is NOT a hard API billing cap. The meter is an estimate and cannot read your real OpenAI balance. Streamlit storage may reset on redeploy. Keep auto-reload OFF and verify the real balance before every new run.')
    try: secret_key=st.secrets.get('OPENAI_API_KEY','')
    except Exception: secret_key=''
    if not secret_key: st.info('Add OPENAI_API_KEY in Streamlit Secrets.')
    d=ledger()
    st.metric('Estimated cumulative API cost (local)',f"US${d['estimated_usd']:.4f} / US${LIMIT:.2f}")
    st.caption(f"Recorded requests: {d['calls']}; pending reserve: US${d.get('in_flight_usd',0):.2f}. This is NOT the actual account balance. Past deployments and other apps may not be counted.")
    names=list(records)
    eligible=bool(secret_key) and len(names)==2 and all(len(records[x])>=16 for x in names) and d['estimated_usd']+d.get('in_flight_usd',0)+RESERVE_PER_CALL<=LIMIT
    st.caption('Before running, check the actual prepaid credit on platform.openai.com. This app cannot enforce a €5 account-wide ceiling.')
    if st.button('Run fully automatic discovery and validation',type='primary',disabled=not eligible):
        try:
            with st.spinner('Analyzing and validating individual photographs…'):
                status=st.empty()
                result=run_pipeline(secret_key,records,get_image,lambda message:status.info(message))
                st.session_state['v3_result']=result
                status.success('Analysis finished')
        except Exception as e:
            st.error(f'Analysis stopped: {e}. Check the actual API balance before trying again.')
    if not eligible: st.info('Requires 16 photos per species, a saved API key and enough local estimated budget for the next request.')
    if 'v3_result' in st.session_state:
        r=st.session_state['v3_result']
        good=[c for c in r['candidates'] if c.get('accepted')]
        st.write(f"**Held-out result:** {len(good)} of {len(r['candidates'])} candidates passed the preset threshold.")
        for c in r['candidates']:
            st.markdown(f"**{c.get('name','Trait')}** — {'Passed' if c.get('accepted') else 'Not supported'}")
            st.write(c.get('question',''))
            st.table([{'species':n,**counts} for n,counts in c['counts'].items()])
            if c.get('card'):
                x=c['card'];item=x['photo'];loc=x['location']
                try:
                    png=draw(get_image(item['url']),x['species'],[{'x_pct':loc['x_pct'],'y_pct':loc['y_pct'],'label':loc.get('label',c['name'])}],item.get('attribution') or item.get('observer',''))
                    st.image(png,caption=f"{item['link']} · license {item['license']} · candidate, not validated",use_container_width=True)
                    st.download_button('Download annotated PNG',png,file_name=x['species'].replace(' ','_')+'_v3.png',mime='image/png',key='dl_'+c['name'])
                except Exception as e: st.warning(f'Could not render card: {e}')
        if not good: st.info('No automatically supported traits found. No misleading annotation has been created.')
        export=json.loads(json.dumps(r,default=str))
        for c in export['candidates']: c.pop('card',None)
        st.download_button('Download analysis JSON',json.dumps(export,indent=2),file_name='moth_discovery_v3.json',mime='application/json')
with tab1:
    st.write('Compare independent individuals. Click the observation links to check identification and image context.')
    left,right=st.columns(2)
    for col,(name,items) in zip((left,right),records.items()):
        with col:
            st.subheader(name)
            for i,item in enumerate(items):
                try:st.image(get_image(item['url']),use_container_width=True)
                except Exception:st.warning('Photo unavailable');continue
                st.caption(f"{i+1}. {item['attribution'] or item['observer']} · license: {item['license']} · [observation]({item['link']})")
with tab2:
    st.warning('Image-wide color/contrast statistics are exploratory. They cannot discover anatomical diagnostic traits by themselves.')
    if st.button('Calculate exploratory image statistics'):
        with st.spinner('Analyzing downloaded photographs…'):
            st.session_state['report']=report(records)
    if st.session_state.get('report'):
        st.markdown(st.session_state['report'])
        st.download_button('Download comparison report',st.session_state['report'],'blind_comparison.md','text/markdown')
    st.subheader('Record hypotheses before consulting literature')
    for name in records:
        st.text_area(f'Visible recurring characters — {name}',key='notes_'+name,placeholder='Wing shape, cross-lines, spots, posture; note exceptions and uncertain images…')
    notes='\n\n'.join(f'## {name}\n{st.session_state.get("notes_"+name,"")}' for name in records)
    st.download_button('Download blind notes',notes,'blind_notes.md')
with tab3:
    name=st.selectbox('Species',list(records))
    items=records[name]
    if items:
        idx=st.selectbox('Reference photo',range(len(items)),format_func=lambda i:f'{i+1} — {items[i]["observer"]}')
        item=items[idx]
        try:
            original=Image.open(io.BytesIO(get_image(item['url']))).convert('RGB')
            st.image(original,caption='Original photograph — choose feature locations using percentages below',width=650)
            st.caption('Coordinates are percentages of the original image, measured from its top-left corner. Markers are manual: automatic anatomical localization is not implemented.')
            with st.form('annotations'):
                labels=[]
                for k in range(1,4):
                    st.markdown(f'**Feature {k}**')
                    label=st.text_input('Description',key=f'label_{k}')
                    x=st.slider('X position (%)',0,100,50,key=f'x_{k}')
                    y=st.slider('Y position (%)',0,100,50,key=f'y_{k}')
                    if label:labels.append((label,x,y))
                submitted=st.form_submit_button('Generate recognition card')
            if submitted:
                im=original.copy(); draw=ImageDraw.Draw(im)
                scale=max(1,im.width/800); radius=int(12*scale); thick=max(2,int(3*scale))
                for j,(label,x,y) in enumerate(labels):
                    px=int(x/100*im.width);py=int(y/100*im.height)
                    draw.ellipse((px-radius,py-radius,px+radius,py+radius),outline='#ed3030',width=thick)
                    draw.line((px+radius,py-radius,px+radius*3,py-radius*3),fill='#ed3030',width=thick)
                    draw.text((px+radius*3+4,py-radius*3-10),str(j+1),fill='#ed3030',stroke_width=2,stroke_fill='white')
                footer=140+len(labels)*38
                card=Image.new('RGB',(im.width,im.height+footer),'white');card.paste(im,(0,0))
                d=ImageDraw.Draw(card);d.text((18,im.height+15),name,fill='black')
                for j,(label,_,_) in enumerate(labels):d.text((18,im.height+48+j*38),f'{j+1}. {label}',fill='black')
                d.text((18,card.height-22),'Candidate characters — NOT validated',fill='#aa3333')
                st.image(card,use_container_width=True)
                output=io.BytesIO();card.save(output,format='PNG')
                st.download_button('Download annotated PNG',output.getvalue(),f'{name.replace(" ","_")}_card.png','image/png')
                metadata={'species':name,'observation':item['link'],'attribution':item['attribution'],'license':item['license'],'characters':[{'label':l,'x_pct':x,'y_pct':y,'status':'unvalidated'} for l,x,y in labels]}
                st.download_button('Download attribution and feature data',json.dumps(metadata,indent=2),'recognition_card.json','application/json')
        except Exception as e:st.error(f'Unable to display photo: {e}')
st.divider()
st.caption('Experimental research tool. Respect image licenses, verify every character independently, and credit photographers when publishing.')
