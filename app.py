import io, json
import requests
import streamlit as st
from PIL import Image
from vision import inspect,png

st.set_page_config(page_title='Moth visual structures v6',layout='wide')
st.title('🦋 Moth visual structures — v6')
st.caption('One species • image measurements only • no OpenAI API • no manual feature selection')
st.warning('Technical proof of concept. Green outlines show estimated foreground; red circles show local dark regions. These are **not** yet biological or species-diagnostic traits. Backgrounds, shadows and folded wings may produce false detections.')

@st.cache_data(ttl=86400,show_spinner=False)
def fetch(name,n):
    response=requests.get('https://api.inaturalist.org/v1/observations',params={'taxon_name':name,'quality_grade':'research','photos':'true','per_page':min(200,n*5),'order_by':'observed_on','order':'desc'},timeout=35,headers={'User-Agent':'MothVisualStructures/0.6 research'})
    response.raise_for_status()
    items=[];users=set()
    for ob in response.json().get('results',[]):
        if (ob.get('taxon') or {}).get('name','').lower()!=name.lower():continue
        user=(ob.get('user') or {}).get('login')
        if user in users:continue
        for p in ob.get('photos') or []:
            url=(p.get('url') or '').replace('square.','large.').replace('medium.','large.')
            if url:
                items.append({'id':ob['id'],'url':url,'link':f"https://www.inaturalist.org/observations/{ob['id']}",'credit':p.get('attribution',''),'license':p.get('license_code','unknown')})
                users.add(user);break
        if len(items)>=n:break
    return items

@st.cache_data(ttl=86400,show_spinner=False)
def download(url):
    r=requests.get(url,timeout=25,headers={'User-Agent':'MothVisualStructures/0.6 research'});r.raise_for_status()
    if len(r.content)>12_000_000:raise ValueError('Photo too large')
    Image.open(io.BytesIO(r.content)).verify()
    return r.content

with st.sidebar:
    st.header('Sample')
    name=st.text_input('Species',value='Noctua pronuba')
    n=st.slider('Photos',4,50,16)
    start=st.button('Fetch and analyze photos',type='primary',use_container_width=True)
    st.caption('Free computer-vision analysis; no OpenAI key or paid API calls.')

if start:
    try:
        with st.spinner('Fetching and measuring visible image structures…'):
            records=fetch(name,n)
            results=[]
            bar=st.progress(0)
            for i,r in enumerate(records):
                try:
                    result=inspect(download(r['url']))
                    if result:results.append((r,result))
                except Exception:pass
                bar.progress((i+1)/len(records))
            st.session_state['analysis']={'species':name,'results':results}
    except Exception as e:st.error(f'Unable to fetch photos: {e}')

analysis=st.session_state.get('analysis')
if not analysis or analysis['species']!=name:
    st.info('Click **Fetch and analyze photos** to run the free proof of concept.');st.stop()
results=analysis['results']
st.write(f'**{len(results)} usable segmentations** (of {n} requested). A segmentation is not necessarily correct.')
if not results:st.stop()
ratios=[v['ratio'] for _,v in results]
st.metric('Median foreground bounding-box elongation',f'{sorted(ratios)[len(ratios)//2]:.2f}×')
st.caption('This number describes the detected silhouette, not the anatomical length of a forewing. Counts of dark regions are sensitive to shadows, exposure and background.')
export=[]
for i in range(0,len(results),3):
    cols=st.columns(3)
    for col,(record,r) in zip(cols,results[i:i+3]):
        with col:
            st.image(r['image'],use_container_width=True)
            st.caption(f"[Observation {record['id']}]({record['link']}) · {len(r['spots'])} local dark regions · silhouette ratio {r['ratio']}×")
            st.caption(f"{record['credit']} · license {record['license']}")
            st.download_button('Download overlay',png(r['image']),file_name=f"moth_{record['id']}_overlay.png",mime='image/png',key=f"download_{i}_{record['id']}")
        export.append({'observation_id':record['id'],'observation_url':record['link'],'credit':record['credit'],'license':record['license'],'silhouette_ratio':r['ratio'],'foreground_coverage':r['coverage'],'local_dark_regions':r['spots']})
st.download_button('Download measurements JSON',json.dumps({'species':name,'method':'GrabCut central foreground + local contrast components; experimental','observations':export},indent=2),file_name='moth_visual_measurements_v6.json',mime='application/json')
st.info('Next research gate: confirm that the green outlines actually follow the moths and that red marks are on wings rather than background. Only then is it meaningful to compare normalized positions across specimens. This version deliberately does not invent recurring anatomical traits.')
