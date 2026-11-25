"""Explicit time alignment, partitioning and operating-point maps."""
import uuid
import numpy as np
from engine import Channel, paired

def align_recordings(a,b,offset=0.):
    """Interpolate B onto A only after the operator explicitly declares clock offset.
    Refuse downsampling, extrapolation, missing data and nonmonotonic clocks.
    """
    if a.time_unit!="s" or b.time_unit!="s" or a.unit!=b.unit:
        raise ValueError("Both channels require seconds and identical engineering units")
    if not np.isfinite(offset) or len(a.y)<2 or len(b.y)<2:
        raise ValueError("Invalid offset or insufficient samples")
    if not np.isfinite(a.y).all() or not np.isfinite(b.y).all():
        raise ValueError("Alignment requires finite input data")
    ta=a.t;tb=b.t+offset
    da=np.diff(ta);db=np.diff(tb)
    if not np.isfinite(tb).all() or not np.all(da>0) or not np.all(db>0):
        raise ValueError("Strictly increasing time is required")
    if np.max(da)>np.min(db)*(1+1e-6):
        raise ValueError("Potential downsampling; anti-alias filtering required before alignment")
    keep=(ta>=tb[0])&(ta<=tb[-1]);t=ta[keep]
    if len(t)<2:raise ValueError("Insufficient overlapping samples")
    key="explicit-alignment:"+uuid.uuid4().hex
    def make(c,y):
        return Channel(c.name+" aligned",y,t,c.unit,"s",dict(c.metadata,clock_id=key,alignment_offset_seconds=offset))
    return make(a,a.y[keep]),make(b,np.interp(t,tb,b.y))

def split_channel(c,index):
    if type(index) is not int or not 0<index<len(c.y):raise ValueError("Split index must be inside the recording")
    return tuple(Channel(c.name+suffix,c.y[s],c.t[s],c.unit,c.time_unit,dict(c.metadata)) for suffix,s in ((" part 1",slice(None,index)),(" part 2",slice(index,None))))

def concatenate_channels(a,b):
    if a.unit!=b.unit or a.time_unit!=b.time_unit or not len(a.y) or not len(b.y):
        raise ValueError("Both recordings need matching units and nonempty samples")
    if not np.all(np.diff(a.t)>0) or not np.all(np.diff(b.t)>0) or b.t[0]<=a.t[-1]:
        raise ValueError("Segments must have strictly increasing, nonoverlapping time coordinates")
    ca=a.metadata.get("clock_id");cb=b.metadata.get("clock_id")
    if ca!=cb:raise ValueError("Segments have different clock origins; align explicitly first")
    return Channel(a.name+" + "+b.name,np.concatenate((a.y,b.y)),np.concatenate((a.t,b.t)),a.unit,a.time_unit,dict(a.metadata))

def efficiency_map(speed,torque,pin,pout,bins=16,minimum_input=.01,minimum_count=3):
    for c in (torque,pin,pout):paired(speed,c)
    if type(bins) is not int or not 2<=bins<=64 or minimum_input<=0 or minimum_count<1 or not np.isfinite(minimum_input):
        raise ValueError("Invalid map parameters")
    x,y,pi,po=(c.y for c in (speed,torque,pin,pout))
    keep=np.isfinite(x)&np.isfinite(y)&np.isfinite(pi)&np.isfinite(po)&(pi>=minimum_input)&(po>=0)
    if keep.sum()<minimum_count:raise ValueError("Insufficient valid motoring samples")
    x,y,pi,po=x[keep],y[keep],pi[keep],po[keep]
    count,xe,ye=np.histogram2d(x,y,bins=bins)
    ips,_,_=np.histogram2d(x,y,bins=[xe,ye],weights=pi)
    ops,_,_=np.histogram2d(x,y,bins=[xe,ye],weights=po)
    z=np.full_like(ips,np.nan)
    np.divide(100*ops,ips,out=z,where=(count>=minimum_count)&(ips>0))
    return xe,ye,z,count
