import struct
def exports(path):
    b=path.read_bytes();pe=struct.unpack_from('<I',b,60)[0];_,sections,_,_,_,size,_=struct.unpack_from('<HHIIIHH',b,pe+4);opt=pe+24;magic=struct.unpack_from('<H',b,opt)[0];directory=opt+(112 if magic==0x20b else 96);table=opt+size
    def offset(rva):
        for i in range(sections):
            vs,va,rawsz,raw=struct.unpack_from('<4I',b,table+i*40+8)
            if va<=rva<va+max(vs,rawsz):return raw+rva-va
        raise ValueError('Unmapped export RVA')
    rva=struct.unpack_from('<I',b,directory)[0];e=struct.unpack_from('<IIHHIIIIIII',b,offset(rva));names=offset(e[9]);result=[]
    for i in range(e[7]):
        n=offset(struct.unpack_from('<I',b,names+i*4)[0]);result.append(b[n:b.index(0,n)].decode())
    return result
