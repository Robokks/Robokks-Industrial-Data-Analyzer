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

def catalog(path):
    from nptdms import TdmsFile
    with TdmsFile.open(path) as f:
        return [(g.name,c.name,len(c),str(c.properties.get("unit_string","")),str(c.dtype)) for g in f.groups() for c in g.channels() if np.dtype(c.dtype).kind in "biuf"]

def tdms_range(path,group,name,start,stop):
    from nptdms import TdmsFile
    with TdmsFile.open(path) as f:
        c=f[group][name]
        if np.dtype(c.dtype).kind not in "biuf" or not 0<=start<stop<=len(c) or stop-start>MAX_SAMPLES:raise ValueError("Invalid or oversized TDMS sample range")
        y=np.asarray(c[start:stop],dtype=float)
        p=c.properties
        dt=p.get("wf_increment");offset=p.get("wf_start_offset",0.)
        meta={"group":group,"channel":name,"properties":{str(k):str(v) for k,v in p.items()},"source":str(path),"range":[start,stop]}
        if dt is not None and np.isfinite(dt) and dt>0 and np.isfinite(offset):
            t=offset+np.arange(start,stop,dtype=float)*dt;unit="s"
            meta["time_source"]="Waveform (range)"
            meta["clock_id"]=f"{Path(path).resolve()}:{group}:{p.get('wf_start_time','relative origin unverified')}"
        else:
            t=np.arange(start,stop,dtype=float);unit="sample"
            meta["time_source"]="Sample index (range; timestamp mapping requires full import)"
            meta["clock_id"]=f"{Path(path).resolve()}:{group}:{name}:index"
        return Channel(f"{Path(path).name}/{group}/{name}",y,t,str(p.get("unit_string","")),unit,meta)

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

def load_record(spec):
    path=Path(spec["path"])
    if not path.is_file():raise ValueError(f"Recording not found: {path.name}")
    if spec.get("range") is not None:
        group,name,start,stop=spec["range"]
        return [tdms_range(path,group,name,start,stop)]
    if path.stat().st_size>MAX_IMPORT_BYTES:raise ValueError("File exceeds full-import size limit; use TDMS range browser")
    if path.suffix.lower() in (".xlsx",".xlsm"):
        with zipfile.ZipFile(path) as archive:
            info=archive.infolist()
            if len(info)>10000 or sum(x.file_size for x in info)>MAX_IMPORT_BYTES:raise ValueError("Excel archive exceeds expanded size limit")
    if path.suffix.lower()==".tdms":
        meta=catalog(path)
        if len(meta)>MAX_CHANNELS or sum(x[2] for x in meta)>MAX_SAMPLES:raise ValueError("TDMS exceeds in-memory budget; use range browser")
    channels=load(path,**spec.get("options",{}))
    if not channels:raise ValueError("No numeric channels")
    for c in channels:
        c.name=f"{path.name}/{c.name}"
        c.metadata["source"]=str(path)
        # Prevent accidental cross-file alignment, including time series with equal coordinates.
        c.metadata["clock_id"]=str(path.resolve())+"|"+c.metadata.get("clock_id","recording")
    return channels

def load_workspace(specs,cancelled=lambda:False):
    if not 1<=len(specs)<=32:raise ValueError("Choose 1–32 recordings")
    all_channels=[];samples=0
    for spec in specs:
        if cancelled():raise InterruptedError("Cancelled")
        channels=load_record(spec)
        samples+=sum(len(c.y) for c in channels)
        if samples>MAX_SAMPLES or len(all_channels)+len(channels)>MAX_CHANNELS:raise ValueError("Working set exceeds budget; use smaller ranges")
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
        if set(s)-{"path","options","range"}:raise ValueError("Unexpected recording fields")
        if Path(s["path"]).suffix.lower() not in (".tdms",".csv",".txt",".xls",".xlsx",".xlsm"):raise ValueError("Unsupported recording format")
        o=s.get("options",{})
        if not isinstance(o,dict) or set(o)-{"sheet","delimiter","time_column","sample_rate","header"}:raise ValueError("Invalid import options")
        if o.get("delimiter") not in (None,",","\t",";",r"\|"):raise ValueError("Unsupported workspace delimiter")
        for key,value in o.items():
            if value is not None and type(value) not in (str,int,float):raise ValueError("Invalid import option")
            if isinstance(value,str) and len(value)>256:raise ValueError("Import option too long")
        if s.get("range") is not None:
            r=s["range"]
            if not isinstance(r,list) or len(r)!=4 or not all(isinstance(x,str) and len(x)<=1024 for x in r[:2]) or not all(type(x) is int for x in r[2:]) or not 0<=r[2]<r[3] or r[3]-r[2]>MAX_SAMPLES or Path(s["path"]).suffix.lower()!=".tdms":raise ValueError("Invalid TDMS range")
    selected=p.get("selected",[]);colors=p.get("colors",{})
    if not isinstance(selected,list) or len(selected)>MAX_CHANNELS or not all(type(x) is int and 0<=x<MAX_CHANNELS for x in selected):raise ValueError("Invalid selection")
    if not isinstance(colors,dict) or len(colors)>MAX_CHANNELS or not all(isinstance(k,str) and k.isdigit() and int(k)<MAX_CHANNELS and isinstance(v,str) and len(v)==7 and v.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in v[1:]) for k,v in colors.items()):raise ValueError("Invalid trace colors")
    return p
