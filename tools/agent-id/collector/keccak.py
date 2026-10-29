MASK=(1<<64)-1

RC=[1,0x8082,0x800000000000808a,0x8000000080008000,0x808b,0x80000001,0x8000000080008081,0x8000000000008009,0x8a,0x88,0x80008009,0x8000000a,0x8000808b,0x800000000000008b,0x8000000000008089,0x8000000000008003,0x8000000000008002,0x8000000000000080,0x800a,0x800000008000000a,0x8000000080008081,0x8000000000008080,0x80000001,0x8000000080008008]

ROT=[[0,36,3,41,18],[1,44,10,45,2],[62,6,43,15,61],[28,55,25,21,56],[27,20,39,8,14]]

def rol(x,n):return ((x<<n)|(x>>(64-n if n else 64)))&MASK

def keccak(data):
    data=bytearray(data);data.append(1)
    while len(data)%136!=135:data.append(0)
    data.append(128);a=[0]*25
    for off in range(0,len(data),136):
        for j in range(17):a[j]^=int.from_bytes(data[off+j*8:off+j*8+8],'little')
        for rc in RC:
            C=[a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20] for x in range(5)]
            D=[C[(x-1)%5]^rol(C[(x+1)%5],1) for x in range(5)]
            for x in range(5):
                for y in range(5):a[x+5*y]^=D[x]
            b=[0]*25
            for x in range(5):
                for y in range(5):b[y+5*((2*x+3*y)%5)]=rol(a[x+5*y],ROT[x][y])
            for x in range(5):
                for y in range(5):a[x+5*y]=b[x+5*y]^((~b[(x+1)%5+5*y])&b[(x+2)%5+5*y])
            a[0]^=rc
    return b''.join(x.to_bytes(8,'little') for x in a)[:32].hex()

def selector(sig):return '0x'+keccak(sig.encode())[:8]

assert selector('totalSupply()')=='0x18160ddd'

assert selector('balanceOf(address)')=='0x70a08231'

assert selector('Registered(bytes32,address,string)')=='0x663d34a8'
