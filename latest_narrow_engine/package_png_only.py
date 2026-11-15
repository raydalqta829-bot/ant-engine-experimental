import json,zipfile,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).parent;OUT=ROOT/'DELIVERY_IMAGES';OUT.mkdir(exist_ok=True)
selected=json.loads((ROOT/'SELECTED.json').read_text());verified=json.loads((ROOT/'VERIFIED.json').read_text());assert len(selected)==3 and all(r['accepted'] for r in verified['cases'].values())
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def f(n,b=False):return ImageFont.truetype(bold if b else font,n)
ink='#213f36';muted='#596a63'
titles={'A':'A | COMPACT CENTRAL LIVING','B':'B | EAST BEDROOM WING','C':'C | REAR KITCHEN / LONGER PLAN'}
notes={'A':'Both ground bedrooms behind the living room.','B':'Second ground bedroom moves to the east side.','C':'Kitchen and service wing move to the rear.'}
for label,name in selected.items():
 for floor in ['GROUND','FIRST']:
  source=ROOT/name/(floor+'.png')
  with Image.open(source) as pic:pic.verify()
  shutil.copyfile(source,OUT/(label+'_'+floor+'.png'))
for idx,floor in enumerate(['GROUND','FIRST']):
 im=Image.new('RGB',(4800,2680),'#f3f1eb');d=ImageDraw.Draw(im)
 d.text((75,48),'ANT | THREE NARROW-SITE VARIANTS - '+floor+' FLOOR',font=f(64,True),fill=ink)
 d.text((75,145),'Same 22 x 40 m south-street site. Same programme and assumed 3 m setbacks. No furniture.',font=f(39),fill=muted)
 if floor=='GROUND':brief='2 ground bedrooms, guest majlis + WC, living, dining, kitchen, store, ensuite + family bath, two entries.'
 else:brief='3 child bedrooms + master with ensuite, family lounge, family bath and terrace; same stair core below.'
 d.text((75,208),brief,font=f(36),fill=muted)
 for i,(label,name) in enumerate(selected.items()):
  x=55+i*1580
  d.rounded_rectangle((x,300,x+1535,2430),radius=22,fill='white')
  d.text((x+30,330),titles[label],font=f(38,True),fill=ink)
  pic=Image.open(ROOT/name/(floor+'.png')).convert('RGB')
  pic.thumbnail((1475,1840),Image.Resampling.LANCZOS)
  im.paste(pic,(x+30+(1475-pic.width)//2,410+(1840-pic.height)//2))
  d.text((x+32,2280),notes[label],font=f(29),fill=ink)
  d.text((x+32,2340),'Programme, geometry and sampled privacy checks: PASS',font=f(27,True),fill='#397558')
 d.text((75,2480),'Different contact layouts: verified beyond rotation or reflection. Plans fitted individually; no common drawing scale.',font=f(35),fill=ink)
 d.text((75,2540),'Preliminary research: column and shaft reservations only; no structural or local-code approval. Architectural review remains required.',font=f(32),fill=muted)
 d.text((75,2600),'Compiler warnings retained: omitted fixtures, solar orientation; C also has an annotation-overlap warning. Published site and A2 unchanged.',font=f(29),fill=muted)
 im.save(OUT/(f'0{idx}_COMPARE_'+floor+'.png'),optimize=True)
archive=ROOT.parent/'ANT_NARROW_THREE_VARIANTS_IMAGES.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(OUT.glob('*.png')):z.write(p,p.name)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==8
 assert all(Path(n).suffix=='.png' for n in z.namelist())
 for n in z.namelist():
  with z.open(n) as src:Image.open(src).verify()
print(json.dumps({'zip':str(archive),'png_images':8,'bytes':archive.stat().st_size,'variants':3,'declared_checks':'passed','structural_approval':False}))
