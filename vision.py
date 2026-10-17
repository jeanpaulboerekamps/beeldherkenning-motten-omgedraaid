import io
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def inspect(raw):
    image=Image.open(io.BytesIO(raw)).convert('RGB')
    image.thumbnail((900,900))
    rgb=np.array(image)
    h,w=rgb.shape[:2]
    if min(h,w)<110: return None
    bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
    # GrabCut estimates the foreground from the central portion of the photograph.
    # It is NOT a trained insect detector: poor crops/backgrounds can cause failures.
    margin_x=max(4,int(w*.055));margin_y=max(4,int(h*.055))
    rect=(margin_x,margin_y,w-2*margin_x,h-2*margin_y)
    mask=np.zeros((h,w),np.uint8)
    bg=np.zeros((1,65),np.float64);fg=np.zeros((1,65),np.float64)
    try:
        cv2.grabCut(bgr,mask,rect,bg,fg,4,cv2.GC_INIT_WITH_RECT)
        fgmask=np.uint8((mask==2)|(mask==3))*255
    except cv2.error:
        return None
    num,lab,stats,_=cv2.connectedComponentsWithStats(fgmask)
    comps=[i for i in range(1,num) if stats[i,cv2.CC_STAT_AREA]>.04*w*h]
    if not comps:return None
    chosen=max(comps,key=lambda i:stats[i,cv2.CC_STAT_AREA])
    fgmask=np.uint8(lab==chosen)*255
    fgmask=cv2.morphologyEx(fgmask,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
    contours,_=cv2.findContours(fgmask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not contours:return None
    cnt=max(contours,key=cv2.contourArea)
    area=cv2.contourArea(cnt)
    coverage=area/(w*h)
    if coverage<.06 or coverage>.88:return None
    x,y,bw,bh=cv2.boundingRect(cnt)
    # Shape ratio is the foreground bounding rectangle, NOT anatomical wing length.
    ratio=max(bw,bh)/max(1,min(bw,bh))
    gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
    # Dark local structures: pixels darker than their local neighborhood.
    k=max(31,int(min(h,w)*.12)//2*2+1)
    background=cv2.GaussianBlur(gray,(k,k),0)
    contrast=cv2.subtract(background,gray)
    inner=cv2.erode(fgmask,np.ones((13,13),np.uint8))
    valid=contrast[inner>0]
    if len(valid)<100:return None
    threshold=max(24,int(np.percentile(valid,94)))
    dark=np.uint8((contrast>=threshold)&(inner>0))*255
    dark=cv2.morphologyEx(dark,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    contours,_=cv2.findContours(dark,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    spots=[]
    for c in contours:
        a=cv2.contourArea(c)
        if a<max(9,area*.00008) or a>area*.025:continue
        mm=cv2.moments(c)
        if not mm['m00']:continue
        cx=int(mm['m10']/mm['m00']);cy=int(mm['m01']/mm['m00'])
        spots.append({'x':cx,'y':cy,'area':round(a,1),'contrast':int(contrast[cy,cx])})
    spots=sorted(spots,key=lambda s:s['area']*s['contrast'],reverse=True)[:8]
    # Diagnostic overlays explicitly show what the algorithm measured.
    overlay=rgb.copy()
    cv2.drawContours(overlay,[cnt],-1,(20,200,100),2)
    for j,s in enumerate(spots,1):
        cv2.circle(overlay,(s['x'],s['y']),10,(240,65,65),2)
        cv2.putText(overlay,str(j),(s['x']+10,s['y']-10),cv2.FONT_HERSHEY_SIMPLEX,.65,(240,65,65),2)
    return {'image':Image.fromarray(overlay),'mask':Image.fromarray(fgmask),'spots':spots,'coverage':round(coverage,3),'ratio':round(ratio,2),'dimensions':(w,h)}

def png(image):
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()
