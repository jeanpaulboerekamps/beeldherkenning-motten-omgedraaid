import io, json, os
from collections import Counter
import requests
import streamlit as st
from PIL import Image
from engine import describe, summarize, check, annotate, ledger, LIMIT_USD

st.set_page_config(page_title='Moth feature discovery v5',layout='wide')
st.title('🦋 Moth feature discovery — v5')
st.caption('Single species • photo-only observation • no manual intervention • experimental')
st.warning('The app finds recurring **descriptive** features, NOT proven species-diagnostic characters. An AI model may still use prior knowledge; every proposed feature is independently checked on held-out images.')
API='https://api.inaturalist.org/v1/observations'
@st.cache_data(ttl=86400,show_spinner=False)
def fetch(name,n):
    r=requests.get(API,params={'taxon_name':name,'quality_grade':'research','photos':'true','per_page':min(200,n*5),'order':'desc','order_by':'observed_on'},timeout=35,headers={'User-Agent':'MothFeatureDiscovery/0.5 educational'})
    r.raise_for_status();items=[];seen=set()
    for ob in r.json().get('results',[]):
        if (ob.get('taxon') or {}).get('name','').lower()!=name.lower():continue
        user=(ob.get('user') or {}).get('login')
        if user in seen:continue
        photos=ob.get('photos') or []
        if not photos:continue
        p=photos[0];url=p.get('url') or ''
        if not url:continue
        # Prefer larger image for morphology
        url=url.replace('square.','large.').replace('medium.','large.')
        items.append({'id':str(ob['id']),'url':url,'link':'https://www.inaturalist.org/observations/'+str(ob['id']),'credit':p.get('attribution',''),'license':p.get('license_code','unknown')})
        seen.add(user)
        if len(items)>=n:break
    return items
@st.cache_data(ttl=86400,show_spinner=False)
def photo(url):
    r=requests.get(url,timeout=30,headers={'User-Agent':'MothFeatureDiscovery/0.5 educational'});r.raise_for_status()
    Image.open(io.BytesIO(r.content)).verify()
    return r.content

with st.sidebar:
    st.header('Sample')
    species=st.text_input('Species',value='Noctua pronuba')
    n=st.slider('Photos',12,50,24,2)
    st.caption('12 discovery photos, 12 independent validation photos (when 24 are fetched).')
    load=st.button('Fetch photographs',type='primary',use_container_width=True)
    st.divider()
    d=ledger();st.metric('Local estimated API spend',f"US${d['spent_estimate']:.3f}")
    st.caption(f'Internal stop: US${LIMIT_USD:.2f}. This is NOT a guaranteed billing cap; it does not know earlier v2–v4 costs or other API usage. Check actual prepaid credit; keep auto-reload OFF.')

if load:
    try:
        with st.spinner('Fetching images…'):
            records=fetch(species,n)
            # Pre-fetch now, so no image fetch occurs during paid analysis
            good=[]
            for r in records:
                try:r['raw']=photo(r['url']);good.append(r)
                except Exception:pass
            st.session_state['sample']={'species':species,'items':good}
            st.session_state.pop('result',None)
    except Exception as e:st.error(str(e))
sample=st.session_state.get('sample')
if not sample or sample['species']!=species:
    st.info('Choose one species and click **Fetch photographs**. No API analysis is performed during fetching.')
    st.stop()
items=sample['items'];st.write(f'**{species}: {len(items)} usable downloads**')
with st.expander('Source photos and licensing',expanded=False):
    for r in items:st.markdown(f"[{r['id']}]({r['link']}) — {r['credit']} — {r['license']}")
if len(items)<12:
    st.error('At least 12 photos are needed. Increase sample size or retry.');st.stop()
if st.button('Discover visible features automatically',type='primary',disabled=not bool(st.secrets.get('OPENAI_API_KEY',os.getenv('OPENAI_API_KEY','')))):
    key=st.secrets.get('OPENAI_API_KEY',os.getenv('OPENAI_API_KEY',''))
    try:
        # Keep API usage small. Strict held-out partition: discovery images never used for verification.
        discovery=items[:min(12,len(items)//2)]
        validation=items[len(discovery):len(discovery)+min(12,len(items)-len(discovery))]
        progress=st.progress(0,text='Describing photos separately…')
        desc=[]
        for j,r in enumerate(discovery):
            desc.append(describe(key,r['id'],r['raw']))
            progress.progress((j+1)/(len(discovery)+1)*0.4,text=f'Photo {j+1}/{len(discovery)}')
        candidates=summarize(key,desc)[:3]
        progress.progress(0.46,text='Validating candidates on unseen photographs…')
        verified=[]
        total=max(1,len(candidates)*len(validation));done=0
        for c in candidates:
            checks=[]
            for r in validation:
                checks.append(check(key,c,r['id'],r['raw']))
                done+=1;progress.progress(0.46+0.52*done/total,text=f'Validation {done}/{total}')
            yes=[x for x in checks if x.get('state')=='yes']
            no=[x for x in checks if x.get('state')=='no']
            unknown=[x for x in checks if x.get('state') not in ('yes','no')]
            # Conservative acceptance: at least 5 positive photos and >=70% among visible states.
            supported=len(yes)>=5 and len(yes)/(len(yes)+len(no) or 1)>=0.7
            verified.append({'candidate':c,'checks':checks,'yes':len(yes),'no':len(no),'unknown':len(unknown),'supported':supported})
        st.session_state['result']={'descriptions':desc,'verified':verified,'species':species,'sample_ids':[r['id'] for r in items]}
        progress.progress(1.,text='Finished')
    except Exception as e:st.error(f'Analysis stopped: {e}. Completed requests may still incur API charges.')
result=st.session_state.get('result')
if result and result['species']==species:
    st.subheader('Observed recurring features')
    if not result['verified']:st.info('No recurring candidate features found. No annotation generated.')
    for entry in result['verified']:
        c=entry['candidate'];st.markdown(f"**{c.get('name','Unnamed feature')}** — {'Supported descriptive feature' if entry['supported'] else 'Not sufficiently supported'}")
        st.write(c.get('description',''))
        st.caption(f"Held-out: yes {entry['yes']}, no {entry['no']}, unknown {entry['unknown']}. Unknown is not counted as absent.")
    supported=[v for v in result['verified'] if v['supported']]
    if supported:
        # Choose one held-out photo with the most located, verified positive features.
        best=None;best_feats=[]
        for r in items:
            feats=[]
            for v in supported:
                ch=next((x for x in v['checks'] if x['id']==r['id'] and x.get('state')=='yes' and isinstance(x.get('point'),list)),None)
                if ch:feats.append({'point':ch['point'],'name':v['candidate'].get('name'),'description':v['candidate'].get('description')})
            if len(feats)>len(best_feats):best,best_feats=r,feats
        if best and best_feats:
            img=annotate(best['raw'],best_feats)
            st.subheader('Automatically annotated candidate card')
            st.image(img,use_container_width=True)
            st.caption(f"Source: {best['link']} • {best['credit']} • License: {best['license']}. Annotation positions are AI estimates, not pixel-verified.")
            st.download_button('Download PNG',img,file_name='moth-features-v5.png',mime='image/png')
    else:st.info('No features met the preset consistency rule. The app will not draw misleading arrows.')
    export={k:v for k,v in result.items() if k!='raw'}
    st.download_button('Download analysis JSON',json.dumps(export,indent=2,ensure_ascii=False),file_name='moth-feature-analysis-v5.json',mime='application/json')
