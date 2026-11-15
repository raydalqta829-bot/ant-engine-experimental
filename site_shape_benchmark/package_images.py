from pathlib import Path
import json,shutil,zipfile
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).parent;OUT=ROOT/'images';OUT.mkdir(exist_ok=True)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def f(n,b=False):return ImageFont.truetype(bold if b else font,n)
ink='#213f36';muted='#596a63';green='#36735b';red='#a33f36'
res=json.loads((ROOT/'RESULTS.json').read_text())
assert len(res)==3
for name,stem in [('wide_shallow','02_WIDE'),('near_square','04_SQUARE')]:
 assert res[name]['accepted']
 for floor,label in [('GROUND','GROUND'),('FIRST','FIRST')]:
  im=Image.open(ROOT/name/(floor+'.png'));im.verify()
  shutil.copyfile(ROOT/name/(floor+'.png'),OUT/(stem+'_'+label+'.png'))
# Comparison is a site occupancy diagram at a common geometric scale, not a substitute plan.
W,H=2700,1570
im=Image.new('RGB',(W,H),'#f4f2ec');d=ImageDraw.Draw(im)
d.text((65,45),'ANT | SAME FAMILY PROGRAMME, THREE SITE SHAPES',font=f(43,True),fill=ink)
d.text((65,111),'Ground: 2 bedrooms  |  First: 3 child bedrooms + master, family lounge, 2 baths + terrace',font=f(27),fill=ink)
d.text((65,153),'South street in all cases. Assumed setbacks: 3 m. Site diagrams use the same scale.',font=f(25),fill=muted)
configs=[('narrow_deep','A | NARROW + DEEP',22,40),('wide_shallow','B | WIDE + SHALLOW',40,22),('near_square','C | NEAR SQUARE',30,30)]
colours={'majlis':'#dfd3bd','bedroom':'#dfd8c8','living':'#c6dbcc','dining':'#e7ddc7','kitchen':'#d4dfce','bathroom':'#c7dfdf','storage':'#d9dfd4','hall':'#e8e2d2','stair':'#d2d7dd'}
for i,(name,title,w,h) in enumerate(configs):
 x=55+i*885
 d.rounded_rectangle((x,220,x+860,1340),radius=18,fill='white')
 d.text((x+30,250),title,font=f(32,True),fill=ink)
 d.text((x+30,298),f'Test site: {w} x {h} m',font=f(26),fill=muted)
 scale=17;bx=x+430-w*scale/2;by=1055-h*scale
 def xy(p):return(bx+p[0]*scale,1055-p[1]*scale)
 d.rectangle((bx,by,bx+w*scale,1055),outline=ink,width=3)
 d.rectangle((*xy((3,h-3)),*xy((w-3,3))),outline='#aab6ad',width=2)
 if res[name]['accepted']:
  q=json.loads((ROOT/name/'COORDINATION.json').read_text())
  for r in q['ground']['rooms']:
   d.polygon([xy(p) for p in r['polygon']],fill=colours.get(r['kind'],'#ddd'),outline='#557063',width=2)
  d.text((x+30,1140),'PASS | Declared engineering gates',font=f(27,True),fill=green)
  d.text((x+30,1187),'Same ground layout in B and C.',font=f(25),fill=ink)
  d.text((x+30,1229),'Floor drawings included as separate PNGs.',font=f(24),fill=muted)
 else:
  d.text((x+65,655),'NO ACCEPTED PLAN',font=f(31,True),fill=red)
  d.text((x+30,1140),'FAIL | Current ground model constraints',font=f(26,True),fill=red)
  d.text((x+30,1187),'No fallback or substituted drawing.',font=f(25),fill=ink)
  d.text((x+30,1229),'Architectural impossibility is not proven.',font=f(24),fill=muted)
 d.rectangle((bx,1074,bx+w*scale,1107),fill='#d7dad7')
 d.text((x+310,1073),'SOUTH STREET',font=f(22,True),fill=ink)
d.text((65,1382),'FINDING: Current topology does not yet adapt well to narrow sites.',font=f(35,True),fill=ink)
d.text((65,1438),'Passing geometry is not an architectural quality score. Column positions are preliminary reservations.',font=f(27),fill=muted)
d.text((65,1488),'Site occupancy only above; detailed floor images are separate. No furniture. Published site and A2 unchanged.',font=f(25),fill=muted)
im.save(OUT/'00_SITE_COMPARISON.png',optimize=True)
# Explicit rejection card prevents implying that a missing narrow-site plan was accidentally omitted.
im=Image.new('RGB',(1800,1050),'#f7f4ef');d=ImageDraw.Draw(im)
lines=[('ANT | A - NARROW + DEEP',52,True,ink),('Site test: 22 x 40 m | South street',34,False,muted),('NO ACCEPTED FLOOR PLAN',54,True,red),('Ground search: INFEASIBLE within the current model.',32,False,ink),('This does not prove that the architectural programme is impossible.',29,False,ink),('The solver must expand its permitted layouts before this case can pass.',29,False,ink),('No fallback drawing was substituted. No first-floor plan was issued.',29,False,ink),('Programme retained: 2 ground bedrooms, guest and family entries;',29,False,muted),('upper: 3 child bedrooms + master, 2 baths, family lounge and terrace.',29,False,muted)]
y=65
for idx,(txt,size,b,c) in enumerate(lines):
 d.text((70,y),txt,font=f(size,b),fill=c);y+=100 if idx in [0,1,2] else 80
im.save(OUT/'01_NARROW_RESULT.png',optimize=True)
archive=ROOT.parent/'ANT_SITE_SHAPE_IMAGES.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(OUT.glob('*.png')):z.write(p,p.name)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert len(z.namelist())==6
 assert all(n.lower().endswith('.png') for n in z.namelist())
 for n in z.namelist():
  with z.open(n) as src:Image.open(src).verify()
print(json.dumps({'archive':str(archive),'images':6,'bytes':archive.stat().st_size,'passed':2,'rejected':1}))
