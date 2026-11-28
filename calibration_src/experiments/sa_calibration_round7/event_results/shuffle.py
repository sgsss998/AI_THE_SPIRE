"""The floor-reset RandomXS128 draw and the Java shuffle used by Shining Light."""
MASK=(1<<64)-1
MULT=0x5DEECE66D
JAVA_MASK=(1<<48)-1


def murmur(value):
    value=((value ^ (value>>33))*0xFF51AFD7ED558CCD)&MASK
    value=((value ^ (value>>33))*0xC4CEB9FE1A85EC53)&MASK
    return value ^ (value>>33)


def upgraded_positions(seed,floor,eligible):
    a=murmur(((seed+floor)&MASK) or (1<<63))
    b=murmur(a)
    a ^= (a<<23)&MASK
    drawn=((a ^ b ^ (a>>17) ^ (b>>26))+b)&MASK
    state=(drawn^MULT)&JAVA_MASK
    slots=list(eligible)
    for count in range(len(slots),1,-1):
        while True:
            state=(state*MULT+11)&JAVA_MASK
            bits=state>>17
            if count & (count-1)==0:
                j=(count*bits)>>31
                break
            j=bits%count
            if bits-j+count-1 < (1<<31):
                break
        slots[count-1],slots[j]=slots[j],slots[count-1]
    return tuple(sorted(slots[:2]))
