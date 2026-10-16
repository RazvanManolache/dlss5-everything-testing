"""Convert the common 3D snapshot into a compact, palettized DOS asset pack."""
from pathlib import Path
import hashlib,json,struct,shutil
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dos/assets'


def main():
    source=ROOT/'shared-assets';OUT.mkdir(parents=True,exist_ok=True)
    data=(source/'museum.bin').read_bytes()
    magic,nv,nd,stride=struct.unpack_from('<4I',data)
    assert magic==0x4D555345 and stride==24
    camera=np.frombuffer(data,'<f4',count=6,offset=16).copy()
    draws=np.frombuffer(data,'<u4',count=nd*3,offset=40).reshape(-1,3)
    dtype=np.dtype([('p','<f4',3),('c','u1',4),('uv','<f4',2)])
    original=np.frombuffer(data,dtype,offset=40+nd*12)
    all_vertices=[];all_triangles=[];offset=0
    for first,count,texture in draws:
        v=original[first:first+count]
        # Quantized vertex clustering retains the gallery's geometry/UV seams.
        cell=np.full((len(v),1),.08 if texture<4 else .045 if texture!=23 else .001)
        if texture==15:cell=np.where(v['p'][:,1:2]>camera[4]-.24,.006,.025)
        key=np.c_[np.floor(v['p']/cell),np.floor(v['uv']*8)].astype(np.int32)
        _,inverse=np.unique(key,axis=0,return_inverse=True)
        size=int(inverse.max())+1;weights=np.bincount(inverse)
        values=np.c_[v['p'],v['uv'],v['c'][:,:3].mean(axis=1)/255]
        reduced=np.stack([np.bincount(inverse,weights=values[:,i])/weights for i in range(6)],axis=1).astype('<f4')
        indices=inverse.reshape(-1,3)
        keep=(indices[:,0]!=indices[:,1])&(indices[:,0]!=indices[:,2])&(indices[:,1]!=indices[:,2])
        indices=indices[keep]
        # Identical collapsed triangles need only be submitted once.
        _,unique=np.unique(np.sort(indices,axis=1),axis=0,return_index=True)
        indices=indices[np.sort(unique)]
        tri=np.zeros(len(indices),dtype=np.dtype([('i','<u4',3),('tex','<u2'),('pad','<u2')]))
        tri['i']=indices+offset;tri['tex']=texture
        all_vertices.append(reduced);all_triangles.append(tri);offset+=size
    vertices=np.concatenate(all_vertices);triangles=np.concatenate(all_triangles)
    images=[];alphas=[]
    for i in range(24):
        raw=(source/f'texture_{i}.rgba').read_bytes();w,h=struct.unpack_from('<II',raw)
        im=Image.frombytes('RGBA',(w,h),raw[8:]).resize((256,256),Image.Resampling.BOX)
        images.append(im.convert('RGB'));alphas.append(np.asarray(im)[:,:,3]<100)
    atlas=Image.new('RGB',(64*24,64*3))
    for i,im in enumerate(images):
        small=np.asarray(im.resize((64,64))).astype(float)
        for j,light in enumerate((.45,.7,1.0)):
            atlas.paste(Image.fromarray(np.uint8(small*light)),(i*64,j*64))
    palette_image=atlas.quantize(colors=240,method=Image.Quantize.MEDIANCUT)
    palette=np.asarray(palette_image.getpalette()[:720],dtype=np.uint8).reshape(240,3)
    ui=np.array([[242,245,235],[72,215,230],[255,205,90],[255,100,90],[0,0,0],[17,24,36],
                 [180,185,195],[70,80,100],[0,0,0],[0,0,0],[0,0,0],[0,0,0],
                 [0,0,0],[0,0,0],[0,0,0],[255,0,255]],dtype=np.uint8)
    palette=np.r_[palette,ui]
    # Quantize against scene colours only; index 255 is transparent.
    quant_palette=Image.new('P',(1,1));quant_palette.putpalette(palette[:240].ravel().tolist()+palette[0].tolist()*16)
    maps=[]
    for im,alpha in zip(images,alphas):
        indices=np.asarray(im.quantize(palette=quant_palette,dither=Image.Dither.FLOYDSTEINBERG)).copy()
        indices[indices>=240]=0;indices[alpha]=255;maps.append(indices.tobytes())
    shades=[]
    colors=palette[:240].astype(float)
    for level in range(32):
        targets=palette.astype(float)*(level/31)
        shades.append(np.argmin(((targets[:,None,:]-colors[None,:,:])**2).sum(axis=2),axis=1).astype('u1').tobytes())
    pack=struct.pack('<4I',0x31534F44,len(vertices),len(triangles),24)+camera.astype('<f4').tobytes()
    pack+=palette.tobytes()+b''.join(shades)+vertices.tobytes()+triangles.tobytes()+b''.join(maps)
    (OUT/'GALLERY.DAT').write_bytes(pack)
    shutil.copy2(source/'CREDITS.md',OUT/'CREDITS.md')
    shutil.copytree(source/'licenses',OUT/'licenses',dirs_exist_ok=True)
    report={'source':'shared-assets/museum.bin','source_sha256':hashlib.sha256(data).hexdigest(),
            'original_triangles':nv//3,'triangles':len(triangles),'vertices':len(vertices),
            'texture_count':24,'texture_size':[256,256],'palette_colors':256,
            'asset_bytes':len(pack),'sha256':hashlib.sha256(pack).hexdigest(),
            'method':'World-space vertex clustering with UV seam preservation; finer focused face; real 3D geometry, not a screenshot'}
    (OUT/'provenance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
