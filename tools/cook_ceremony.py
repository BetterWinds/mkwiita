#!/usr/bin/env python3
"""Grand Prix award ceremony, losing scene and ending stage.

Converted once with the 0.5.0 rebuild so the scenes can arrive as quick
updates: the stages (Race/Course/*_demo.szs) through the course importer,
the award characters (Demo/Award.szs: standing model with demowin/demooth),
podium blocks, shadow, trophies (Demo/Trophy) and the ceremony camera moves
(SCN0: 123dai demowin01-03, Lose demolos01). models/ceremony.json lists it all.
"""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'vendor/gclib')]
from unpack_szs import unpack
from cook_model import cook
OUT=ROOT/'sd-card/3ds/mkw-3ds'
EXTRACTED=ROOT/'data/extracted'
WORK=ROOT/'build/ceremony'
# Kinoko course IDs (Common.hh COURSE_NAMES): the scenes' stages.
# draw_demo is not converted: retail's table names it "draw_dmeo", so the game
# never loads it (its textures are also an older TEX0 version).
STAGES=[(55,'winningrun_demo','Winning run'),(56,'loser_demo','Losing'),(58,'ending_demo','Ending')]
DISC_FILES=['Demo/','Race/Course/winningrun_demo.szs','Race/Course/loser_demo.szs','Race/Course/ending_demo.szs']
CUPS=['kinoko','flower','star','special','koura','banana','konoha','thunder','battle']

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def extract(disc):
    missing=[f for f in DISC_FILES if not (EXTRACTED/f).exists()]
    if not missing:return
    if not disc:raise SystemExit('The ceremony files need the disc image: '+', '.join(missing))
    command=[sys.executable,str(ROOT/'tools/extract_disc.py'),str(disc),str(EXTRACTED)]
    for f in DISC_FILES:command+=['--prefix',f]
    subprocess.run(command,check=True)

def export(source,destination,model,*pose,env=None):
    destination.mkdir(parents=True,exist_ok=True)
    subprocess.run(['node',str(ROOT/'build/export_brres.mjs'),str(source),str(destination),model,*pose],check=True,stdout=subprocess.DEVNULL,env=env)

def model_names(path):
    """MDL0 names of a BRRES (its 3DModels group)."""
    import struct
    b=path.read_bytes();root=struct.unpack_from('>H',b,0xc)[0]
    def group(off):
        n=struct.unpack_from('>I',b,off+4)[0];out=[]
        for i in range(1,n+1):
            e=off+8+i*16;name_off,data_off=struct.unpack_from('>II',b,e+8)
            out.append((b[off+name_off:b.index(0,off+name_off)].decode(),off+data_off))
        return out
    groups=dict(group(root+8))
    return [n for n,_ in group(groups['3DModels(NW4R)'])] if '3DModels(NW4R)' in groups else []

def cook_static(source,model,name):
    work=WORK/'exports'/name;export(source,work,model)
    parts=cook(work,OUT,name,256,texture_prefix=name)
    if len(parts)!=1:raise ValueError(f'{name}: expected one model, got {len(parts)}')
    shutil.copyfile(OUT/'models'/(parts[0]['name']+'.gmdl'),OUT/'models'/(name+'.gmdl'))
    return name

def cook_award_character(source,code):
    """Standing award model (bound in its first demowin pose) and its demowin/demooth bank."""
    name='award_'+code;work=WORK/'exports'/name
    # Racer materials (as tools/cook_garage.py): the albedo with the lm_0/lm_1
    # light maps and retail lighting. Without it the untranslated material falls
    # back to its first sampler, lm_1, and the whole body renders as a gradient.
    export(source,work,'model','demowin','0',env={**os.environ,'MKW_RACE_MATERIALS':'1'})
    parts=cook(work,OUT,name,256,preserve_vertices=True,texture_prefix=name)
    if len(parts)!=1:raise ValueError(f'{name}: expected one model, got {len(parts)}')
    shutil.copyfile(OUT/'models'/(parts[0]['name']+'.gmdl'),OUT/'models'/(name+'.gmdl'))
    bank=OUT/'models'/(name+'.dskm')
    audit=json.loads(subprocess.run(['node',str(ROOT/'build/export_driver.mjs'),str(source),str(bank)],check=True,capture_output=True,text=True).stdout)
    clips=[c['name'] if isinstance(c,dict) else c for c in audit['clips']]
    if not {'demowin','demooth'}<={*clips}:raise ValueError(f'{name}: award clips missing ({clips})')
    return {'code':code,'model':f'models/{name}.gmdl','bank':f'models/{name}.dskm','clips':clips}

# The ceremony's words, in the order src/award_ceremony.cpp reads text.bin:
# Race_U Race.bmg's two closing lines, the eight cup names (Award_U Common.bmg),
# RANK: and its eight grades, the three "You got Nth place!" lines and the
# engine classes, in kart_kanji_font as the game draws them.
CUP_NAMES=['Mushroom Cup','Flower Cup','Star Cup','Special Cup','Shell Cup','Banana Cup','Leaf Cup','Lightning Cup']
GRADES=['★★★','★★','★','A','B','C','D','E']
PLACES=['You got 1st place!','You got 2nd place!','You got 3rd place!']
CLASSES=['50cc','100cc','150cc','Mirror']
TEXT=[('congratulations','Congratulations!','Race_U'),('better_luck','Better luck next time!','Race_U'),
      *[(f'cup_{i}',name,'Award_U') for i,name in enumerate(CUP_NAMES)],('rank','RANK:','Race_U'),
      *[(f'grade_{i}',grade,None) for i,grade in enumerate(GRADES)],
      *[(f'place_{i}',text,'Race_U') for i,text in enumerate(PLACES)],
      *[(f'class_{i}',text,None) for i,text in enumerate(CLASSES)],
      # Team VS and Battle standings: the winners' line and the mode at the top left.
      ('team_0','The red team wins!','Race_U'),('team_1','The blue team wins!','Race_U'),
      *[(f'mode_{i}',text,'Race_U') for i,text in enumerate(['Balloon Battle','Coin Runners','Team VS Race'])]]

def bmg_text(data):
    """BMG messages with every escape (U+001A, its byte length, payload: colour,
    icons) as a NUL, so a message wrapped in a colour code ("The red team
    wins!") still matches whole."""
    out=bytearray();i=0
    while i+1<len(data):
        if data[i]==0 and data[i+1]==0x1a and i+2<len(data):
            out+=bytes(2);i+=max(data[i+2],4);continue
        out+=data[i:i+2];i+=2
    return bytes(out)

def cook_text():
    from cook_race_hud import font_strings
    from cook_race_items import cook_image_sprite
    import struct
    font=WORK/'Font';unpack(EXTRACTED/'Scene/UI/Font.szs',font)
    kanji=next(font.rglob('kart_kanji_font.brfnt'))
    messages={}
    for archive in ('Race_U','Award_U'):
        folder=WORK/archive;unpack(EXTRACTED/f'Scene/UI/{archive}.szs',folder)
        messages[archive]=bmg_text(b''.join(p.read_bytes() for p in folder.rglob('*.bmg')))
    for key,text,archive in TEXT:
        # A whole message, or one after an icon and its space (" Team VS Race").
        if archive and not any(('\0'+lead+text+'\0').encode('utf-16-be') in b'\0\0'+messages[archive]+b'\0\0' for lead in ('',' ')):
            raise ValueError(f'{text!r} is not in {archive} messages')
    images=font_strings(kanji,[text for _,text,_ in TEXT])
    rows={key:{**cook_image_sprite(images[text],'ceremony_text_'+key,OUT),'text':text} for key,text,_ in TEXT}
    # text.bin: per string (TEXT order) its width and height in texels, u16.
    (OUT/'models/ceremony/text.bin').write_bytes(b''.join(struct.pack('<2H',rows[k]['width'],rows[k]['height']) for k,_,_ in TEXT))
    return rows

def cook_winning_run():
    """The winning run (winningrun_demo course.kmp) as models/ceremony/winning_run.bin,
    little endian:
    - u32 lanes (3), u32 points per lane, then x, y, z floats: ENPT, one ENPH group
      per podium kart from its KTPT start; each group's last point (the link back
      to the start) is left out;
    - u32 cameras, u32 first, then per CAME entry: u8 type, next, route, 0;
      u16 route speed, FOV speed, view speed, 0; floats position, view start,
      view end, FOV start, FOV end, time;
    - u32 routes, then per POTI route: u32 points, then x, y, z floats and the
      point's speed (setting 0) as a float."""
    import struct
    d=(ROOT/'assets/courses/winningrun_demo/course.kmp').read_bytes()
    n,header=struct.unpack_from('>HH',d,8)
    sections={d[header+o:header+o+4]:header+o for o in struct.unpack_from(f'>{n}I',d,0x10)}
    points,groups=sections[b'ENPT'],sections[b'ENPH']
    lanes=[]
    for g in range(struct.unpack_from('>H',d,groups+4)[0]):
        start,length=d[groups+8+g*16],d[groups+9+g*16]
        lanes.append([struct.unpack_from('>3f',d,points+8+i*20) for i in range(start,start+length-1)])
    if len(lanes)!=3 or len({len(l) for l in lanes})!=1:raise ValueError('Winning run: expected three equal lanes')
    out=struct.pack('<2I',3,len(lanes[0]))+b''.join(struct.pack('<3f',*p) for lane in lanes for p in lane)
    came=sections[b'CAME'];count,first=struct.unpack_from('>HB',d,came+4)
    out+=struct.pack('<2I',count,first)
    for i in range(count):
        e=came+8+i*0x48
        kind,nxt,_,route,path,fov,view=struct.unpack_from('>BBBBHHH',d,e)
        out+=struct.pack('<4B4H',kind,nxt,route,0,path,fov,view,0)+struct.pack('<12f',*struct.unpack_from('>3f',d,e+0x0c),*struct.unpack_from('>3f',d,e+0x2c),*struct.unpack_from('>3f',d,e+0x38),*struct.unpack_from('>2f',d,e+0x24),*struct.unpack_from('>f',d,e+0x44))
    poti=sections[b'POTI'];routes=struct.unpack_from('>H',d,poti+4)[0];q=poti+8
    out+=struct.pack('<I',routes)
    for _ in range(routes):
        length=struct.unpack_from('>H',d,q)[0];q+=4
        out+=struct.pack('<I',length)
        for j in range(length):
            x,y,z,speed,_=struct.unpack_from('>3fHH',d,q+j*16);out+=struct.pack('<4f',x,y,z,float(speed))
        q+=length*16
    (OUT/'models/ceremony/winning_run.bin').write_bytes(out)
    return 'models/ceremony/winning_run.bin'

def main():
    p=argparse.ArgumentParser();p.add_argument('disc',nargs='?');a=p.parse_args()
    extract(a.disc)
    WORK.mkdir(parents=True,exist_ok=True)
    manifest={'version':1,'stages':[],'award':{},'trophies':{},'cameras':[]}
    # Stages: the race course pipeline (models, sky, map, placed objects).
    from import_courses import import_one
    for i,key,name in STAGES:
        c={'id':i,'enum':key,'name':name,'kind':'race','cup':'Ceremony','slot':0,'archive':f'Race/Course/{key}.szs','key':key,'prefix':f'course_{i:02d}'}
        r=import_one(c)
        if r['status']!='imported':raise SystemExit(f'{name} stage: {r.get("error")}')
        manifest['stages'].append({'id':i,'key':key,'name':name,'receipt':f'models/courses/{i:02d}.json','model_lists':r['model_lists'],'object_visuals':r.get('object_visuals')})
    # Award characters (including the Mii bodies and the bike outfits ds3/pc3/rs3),
    # podium blocks and the shared shadow.
    award=WORK/'Award';unpack(EXTRACTED/'Demo/Award.szs',award)
    characters=[]
    # The archive also holds empty folders (Cup, Camera, Model, hiradai2.brres...).
    for source in sorted(p for p in award.glob('*.brres') if p.is_file()):
        models=model_names(source)
        if models==['model']:characters.append(cook_award_character(source,source.stem))
    manifest['award']['characters']=characters
    manifest['award']['stands']=[cook_static(award/'v_stand1.brres',m,'award_'+m) for m in model_names(award/'v_stand1.brres')]
    manifest['award']['shadow']=cook_static(award/'shadow.brres','shadow','award_shadow')
    for cup in CUPS:
        source=EXTRACTED/f'Demo/Trophy/{cup}_trophy.brres'
        manifest['trophies'][cup]=cook_static(source,f'{cup}_trophy',f'trophy_{cup}')
    # Camera moves (tools/ceremony/export_scene.ts).
    subprocess.run(['node','tools/ceremony/bundle.mjs'],cwd=ROOT,check=True)
    lose=WORK/'Lose';unpack(EXTRACTED/'Demo/Lose.szs',lose)
    cameras=OUT/'models/ceremony'
    if cameras.exists():shutil.rmtree(cameras)
    for source in (award/'123dai.brres',lose/'demolos01.brres'):
        out=subprocess.run(['node',str(ROOT/'build/ceremony/export_scene.mjs'),str(source),str(cameras)],check=True,capture_output=True,text=True).stdout
        for row in json.loads(out):manifest['cameras'].append({**row,'file':'models/ceremony/'+row['file']})
    manifest['winningRun']=cook_winning_run()
    manifest['text']=cook_text()
    manifest['sources']={f:digest(EXTRACTED/f) for f in ['Demo/Award.szs','Demo/Lose.szs']+[f'Demo/Trophy/{c}_trophy.brres' for c in CUPS]}
    (OUT/'models/ceremony.json').write_text(json.dumps(manifest,indent=1)+'\n')
    print(f"ceremony: {len(manifest['stages'])} stages, {len(characters)} award characters, {len(manifest['trophies'])} trophies, {len(manifest['cameras'])} camera moves")

if __name__=='__main__':main()
