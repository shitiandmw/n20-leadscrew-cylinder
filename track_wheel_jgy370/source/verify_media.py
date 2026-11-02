"""Decode every video frame and inspect motion samples / PDF pages."""
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
import fitz
ROOT=Path(__file__).resolve().parents[1]

def main():
    gen=imageio_ffmpeg.read_frames(str(ROOT/'J8_operation.mp4'),pix_fmt='rgb24')
    meta=next(gen);w,h=meta['size'];samples={};count=0
    for i,raw in enumerate(gen):
        count=i+1
        if i in [50,180,300,390,450,575,650]:
            a=np.frombuffer(raw,dtype=np.uint8).reshape(h,w,3).copy();samples[i]=a
            Image.fromarray(a).save(ROOT/'images'/f'decoded_{i:04}.jpg',quality=94)
    expected=json.loads((ROOT/'video_validation.json').read_text())
    assert (w,h)==(1280,720) and meta['fps']==25 and count==expected['frame_count']
    # Two distinct times within the forward/reverse chapter, with fixed camera.
    difference=float(np.abs(samples[450][190:600,110:850].astype(float)-samples[575][190:600,110:850]).mean())
    assert difference>1 and all(float(a.std())>10 for a in samples.values())
    pages=[]
    doc=fitz.open(ROOT/'J8_design_review.pdf')
    assert len(doc)==3
    for i,p in enumerate(doc):
        pix=p.get_pixmap(matrix=fitz.Matrix(1.3,1.3));path=ROOT/'images'/f'review_page_{i+1}.png';pix.save(str(path));pages.append(dict(page=i+1,width=pix.width,height=pix.height,extracted_characters=len(p.get_text())))
    report=dict(pass_=True,video=dict(size=[w,h],fps=meta['fps'],frames=count,duration_s=count/meta['fps'],codec=meta.get('codec'),decoded_all_frames=True,
                                    forward_reverse_image_difference=difference),pdf=dict(pages=pages),scope='File decode and motion image checks; visual inspection required separately.')
    report['pass']=report.pop('pass_')
    (ROOT/'media_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
