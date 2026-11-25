"""Bounded display previews and cursor lookup; never used for analysis."""
import math
import numpy as np

def preview_indices(values, limit=4000, backend="numpy"):
    y=np.asarray(values,dtype=float)
    if y.ndim!=1 or limit<4:raise ValueError("Invalid preview input")
    n=len(y)
    if n<=limit:return np.arange(n,dtype=np.intp)
    # Preserve discontinuities rather than connecting across missing samples.
    if not np.isfinite(y).all():return np.arange(n,dtype=np.intp)
    width=math.ceil(n/max(1,(limit-2)//2))
    if backend=="rust":
        from analyzer_native import bucket_extrema
        # Bound temporary Python object allocations; maintain exact bucket boundaries.
        block=width*max(1,65536//width)
        ids=[]
        for start in range(0,n,block):
            ids.extend(start+i for i,_ in bucket_extrema(y[start:start+block].tolist(),width))
        return np.unique(np.r_[0,np.asarray(ids,dtype=np.intp),n-1])
    if backend!="numpy":raise ValueError("Unknown preview backend")
    count=n//width
    starts=np.arange(count,dtype=np.intp)*width
    chunks=y[:count*width].reshape(count,width)
    lo=starts+np.argmin(chunks,axis=1)
    hi=starts+np.argmax(chunks,axis=1)
    tail=y[count*width:]
    extra=[count*width+int(np.argmin(tail)),count*width+int(np.argmax(tail))] if len(tail) else []
    return np.unique(np.r_[0,lo,hi,np.asarray(extra,dtype=np.intp),n-1])

def nearest_index(time, value, ordered=True):
    if not len(time) or not np.isfinite(value):return None
    if not ordered:
        if value<np.min(time) or value>np.max(time):return None
        return int(np.argmin(np.abs(time-value)))
    if value<time[0] or value>time[-1]:return None
    i=int(np.searchsorted(time,value))
    if i==0:return 0
    if i==len(time):return i-1
    return i-1 if value-time[i-1]<=time[i]-value else i

def cursor_measurement(time, values, a, b, ordered=True):
    i=nearest_index(time,a,ordered);j=nearest_index(time,b,ordered)
    if i is None or j is None:return None
    return (float(time[j]-time[i]),float(values[i]),float(values[j]),float(values[j]-values[i]))
