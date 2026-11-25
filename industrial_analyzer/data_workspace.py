"""Metadata-only TDMS browsing and bounded range reads; workspace manifests."""
import json
import os
import tempfile
import zipfile
from pathlib import Path
import numpy as np
from engine import Channel, load

# Limits apply to the selected in-memory working set, not source TDMS file size.
MAX_SAMPLES=8_000_000
MAX_CHANNELS=256
MAX_IMPORT_BYTES=128*1024*1024

class TdmsRangeRequired(ValueError):
    def __init__(self,path,sample_budget,channel_budget):
        self.path=str(Path(path).resolve());self.sample_budget=max(0,sample_budget);self.channel_budget=max(0,channel_budget)
        super().__init__(f"TDMS exceeds in-memory budget: {Path(path).name}. Select channels and a sample range.")

def catalog(path):
    from nptdms import TdmsFile
    with TdmsFile.open(path) as f:
        return [(g.name,c.name,len(c),str(c.properties.get("unit_string","")),str(c.dtype)) for g in f.groups() for c in g.channels() if np.dtype(c.dtype).kind in "biuf" and len(c)>0]

def _read_range(f,path,group,name,start,stop):
    c=f[group][name]
    if np.dtype(c.dtype).kind not in "biuf" or not 0<=start<stop<=len(c) or stop-start>MAX_SAMPLES:
        raise ValueError("Invalid or oversized TDMS sample range")
    y=np.asarray(c[start:stop],dtype=float)
    p=c.properties;dt=p.get("wf_increment");offset=p.get("wf_start_offset",0.)
    meta={"group":group,"channel":name,"properties":{str(k):str(v) for k,v in p.items()},"source":str(path),"range":[start,stop],"source_samples":len(c)}
    prefix=f"{Path(path).resolve()}:{group}"
    if isinstance(dt,(int,float,np.number)) and np.isfinite(dt) and dt>0 and isinstance(offset,(int,float,np.number)) and np.isfinite(offset):
        t=offset+np.arange(start,stop,dtype=float)*dt;unit="s"
        meta["time_source"]="Waveform (range)"
        meta["clock_id"]=f"{prefix}:waveform:{p.get('wf_start_time','relative origin unverified')}"
    else:
        candidates=[]
        for clock in f[group].channels():
            if clock.name==name or len(clock)!=len(c):continue
            kind=np.dtype(clock.dtype).kind;cn=clock.name.strip().casefold();cu=str(clock.properties.get("unit_string","")).strip().casefold()
            numeric=kind in "iuf" and cn in ("time","timestamp","elapsed time","time (s)","time [s]") and (cu in ("s","sec","second","seconds") or cn in ("time (s)","time [s]"))
            if kind!="M" and not numeric:continue
            candidates.append((clock,kind))
        t=None
        if len(candidates)==1:
            clock,kind=candidates[0];raw=np.asarray(clock[start:stop])
            if kind=="M":
                origin=np.asarray(clock[0:1])[0]
                if not np.isnat(origin) and not np.isnat(raw).any():t=(raw-origin)/np.timedelta64(1,"s")
            else:t=raw.astype(float)
            if t is not None and (not np.isfinite(t).all() or not np.all(t[1:]>t[:-1])):t=None
            if t is not None:
                unit="s";meta["time_source"]=f"Timestamp channel: {clock.name} (range)";meta["clock_id"]=f"{prefix}:timestamp:{clock.name}"
        if t is None:
            t=np.arange(start,stop,dtype=float);unit="sample"
            meta["time_source"]="Sample index (no unique valid clock)"
            meta["clock_id"]=f"{prefix}:{name}:index"
    return Channel(f"{Path(path).name}/{group}/{name}",y,t,str(p.get("unit_string","")),unit,meta)

def tdms_range(path,group,name,start,stop):
    from nptdms import TdmsFile
    with TdmsFile.open(path) as f:return _read_range(f,path,group,name,start,stop)

def validate_ranges(ranges,sample_budget,channel_budget):
    if not isinstance(ranges,list) or not 1<=len(ranges)<=channel_budget:raise ValueError(f"Select 1–{channel_budget} channels")
    total=0;seen=set()
    for r in ranges:
        if not isinstance(r,list) or len(r)!=4 or not all(isinstance(x,str) and 0<len(x)<=1024 for x in r[:2]) or not all(type(x) is int for x in r[2:]) or not 0<=r[2]<r[3]:raise ValueError("Invalid TDMS range")
        key=tuple(r[:2])
        if key in seen:raise ValueError("Duplicate channel selection")
        seen.add(key);total+=r[3]-r[2]
        if total>sample_budget:raise ValueError(f"Selected ranges contain more than {sample_budget:,} values. Reduce the channel count or range.")
    return total

def tdms_ranges(path,ranges,sample_budget,channel_budget,cancelled=lambda:False):
    from nptdms import TdmsFile
    validate_ranges(ranges,sample_budget,channel_budget)
    with TdmsFile.open(path) as f:
        # Validate every requested channel/range before allocating arrays.
        for group,name,start,stop in ranges:
            c=f[group][name]
            if np.dtype(c.dtype).kind not in "biuf" or stop>len(c):raise ValueError(f"Range outside channel: {group}/{name}")
        out=[]
        for group,name,start,stop in ranges:
            if cancelled():raise InterruptedError("Cancelled")
            out.append(_read_range(f,path,group,name,start,stop))
        return out

def stream_stats(path,group,name,cancelled=lambda:False):
    """Exact finite count, min/max, population variance and RMS in bounded slices."""
    from nptdms import TdmsFile
    n=missing=0;mean=m2=ss=0.;lo=np.inf;hi=-np.inf
    with TdmsFile.open(path) as f:
        c=f[group][name]
        if np.dtype(c.dtype).kind not in "biuf":raise ValueError("Numeric channel required")
        for start in range(0,len(c),262144):
            if cancelled():raise InterruptedError("Cancelled")
            a=np.asarray(c[start:min(start+262144,len(c))],dtype=float)
            b=a[np.isfinite(a)];missing+=len(a)-len(b)
            if not len(b):continue
            k=len(b);mu=b.mean();delta=mu-mean
            m2+=np.sum((b-mu)**2)+delta**2*n*k/(n+k);mean+=delta*k/(n+k);n+=k
            ss+=np.dot(b,b);lo=min(lo,b.min());hi=max(hi,b.max())
    return {"Valid":n,"Missing":missing,"Min":lo if n else np.nan,"Max":hi if n else np.nan,"Mean":mean if n else np.nan,"Population SD":np.sqrt(m2/n) if n else np.nan,"RMS":np.sqrt(ss/n) if n else np.nan}

def load_record(spec,cancelled=lambda:False,sample_budget=None,channel_budget=None):
    path=Path(spec["path"])
    if not path.is_file():raise ValueError(f"Recording not found: {path.name}")
    sample_budget=MAX_SAMPLES if sample_budget is None else sample_budget
    channel_budget=MAX_CHANNELS if channel_budget is None else channel_budget
    is_tdms=path.suffix.lower()==".tdms"
    ranges=spec.get("ranges")
    if spec.get("range") is not None:
        if ranges is not None:raise ValueError("Conflicting TDMS range fields")
        ranges=[spec["range"]]
    if ranges is not None:
        if not is_tdms:raise ValueError("Ranges require TDMS")
        return tdms_ranges(path,ranges,sample_budget,channel_budget,cancelled)
    if is_tdms:
        if path.stat().st_size>MAX_IMPORT_BYTES:raise TdmsRangeRequired(path,sample_budget,channel_budget)
        meta=catalog(path)
        if len(meta)>channel_budget or sum(x[2] for x in meta)>sample_budget:raise TdmsRangeRequired(path,sample_budget,channel_budget)
    elif path.stat().st_size>MAX_IMPORT_BYTES:raise ValueError("File exceeds full-import size limit")
    if path.suffix.lower() in (".xlsx",".xlsm"):
        with zipfile.ZipFile(path) as archive:
            info=archive.infolist()
            if len(info)>10000 or sum(x.file_size for x in info)>MAX_IMPORT_BYTES:raise ValueError("Excel archive exceeds expanded size limit")
    if cancelled():raise InterruptedError("Cancelled")
    channels=load(path,**spec.get("options",{}))
    if not channels:raise ValueError("No numeric channels")
    if len(channels)>channel_budget or sum(len(c.y) for c in channels)>sample_budget:raise ValueError("Working set exceeds budget; use smaller recordings")
    for c in channels:
        c.name=f"{path.name}/{c.name}";c.metadata["source"]=str(path)
        c.metadata["clock_id"]=str(path.resolve())+"|"+c.metadata.get("clock_id","recording")
    return channels

def load_workspace(specs,cancelled=lambda:False):
    if not 1<=len(specs)<=32:raise ValueError("Choose 1–32 recordings")
    all_channels=[];samples=0
    for spec in specs:
        if cancelled():raise InterruptedError("Cancelled")
        channels=load_record(spec,cancelled,MAX_SAMPLES-samples,MAX_CHANNELS-len(all_channels))
        samples+=sum(len(c.y) for c in channels)
        existing={c.name for c in all_channels}
        for c in channels:
            base=c.name;k=2
            while c.name in existing:c.name=f"{base} [{k}]";k+=1
            existing.add(c.name)
        all_channels.extend(channels)
    return all_channels

def write_manifest(path,specs,selected,colors):
    payload={"version":1,"recordings":specs,"selected":list(selected),"colors":colors}
    fd,temp=tempfile.mkstemp(dir=Path(path).parent,suffix=".json")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(payload,f,indent=2,allow_nan=False)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def read_manifest(path):
    if Path(path).stat().st_size>256*1024:raise ValueError("Workspace manifest exceeds size limit")
    with open(path,encoding="utf-8") as f:p=json.load(f)
    if not isinstance(p,dict) or p.get("version")!=1:raise ValueError("Unsupported workspace version")
    records=p.get("recordings")
    if not isinstance(records,list) or not 1<=len(records)<=32:raise ValueError("Invalid recording list")
    for s in records:
        if not isinstance(s,dict) or not isinstance(s.get("path"),str) or len(s["path"])>4096 or not Path(s["path"]).is_absolute():raise ValueError("Invalid recording path")
        if set(s)-{"path","options","range","ranges"}:raise ValueError("Unexpected recording fields")
        if Path(s["path"]).suffix.lower() not in (".tdms",".csv",".txt",".xls",".xlsx",".xlsm"):raise ValueError("Unsupported recording format")
        o=s.get("options",{})
        if not isinstance(o,dict) or set(o)-{"sheet","delimiter","time_column","sample_rate","header"}:raise ValueError("Invalid import options")
        if o.get("delimiter") not in (None,",","\t",";",r"\|"):raise ValueError("Unsupported workspace delimiter")
        for key,value in o.items():
            if value is not None and type(value) not in (str,int,float):raise ValueError("Invalid import option")
            if isinstance(value,str) and len(value)>256:raise ValueError("Import option too long")
        if s.get("ranges") is not None:
            if s.get("range") is not None or Path(s["path"]).suffix.lower()!=".tdms":raise ValueError("Invalid TDMS range fields")
            validate_ranges(s["ranges"],MAX_SAMPLES,MAX_CHANNELS)
        if s.get("range") is not None:
            r=s["range"]
            if not isinstance(r,list) or len(r)!=4 or not all(isinstance(x,str) and len(x)<=1024 for x in r[:2]) or not all(type(x) is int for x in r[2:]) or not 0<=r[2]<r[3] or r[3]-r[2]>MAX_SAMPLES or Path(s["path"]).suffix.lower()!=".tdms":raise ValueError("Invalid TDMS range")
    selected=p.get("selected",[]);colors=p.get("colors",{})
    if not isinstance(selected,list) or len(selected)>MAX_CHANNELS or not all(type(x) is int and 0<=x<MAX_CHANNELS for x in selected):raise ValueError("Invalid selection")
    if not isinstance(colors,dict) or len(colors)>MAX_CHANNELS or not all(isinstance(k,str) and k.isdigit() and int(k)<MAX_CHANNELS and isinstance(v,str) and len(v)==7 and v.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in v[1:]) for k,v in colors.items()):raise ValueError("Invalid trace colors")
    return p
