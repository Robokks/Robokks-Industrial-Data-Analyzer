"""Opt-in, read-only loopback measurement capture for LabVIEW.

Protocol: UTF-8 JSON object per TCP newline or UDP datagram:
{"t": 0.0, "values": {"Speed": 1500.0, "Torque": 20.0}}
No remote binding, commands, discovery, or outbound data.
"""
import json
import math
import socket
import time
import numpy as np
from engine import Channel

MAX_FRAME=16384
MAX_ROWS=100000
MAX_CHANNELS=64
MAX_VALUES=2_000_000

def parse_frame(data):
    if len(data)>MAX_FRAME:raise ValueError("Frame exceeds limit")
    try:obj=json.loads(data.decode("utf-8"))
    except (UnicodeError,ValueError) as exc:raise ValueError("Malformed measurement JSON") from exc
    if not isinstance(obj,dict) or set(obj)!={"t","values"}:raise ValueError("Expected t and values")
    t=obj["t"];values=obj["values"]
    def numeric(x):
        if type(x) not in (int,float):return False
        try:return math.isfinite(x)
        except OverflowError:return False
    if not numeric(t) or not isinstance(values,dict) or not 1<=len(values)<=MAX_CHANNELS:raise ValueError("Invalid time or channel count")
    if not all(isinstance(k,str) and 1<=len(k)<=80 and k.isprintable() and numeric(v) for k,v in values.items()):raise ValueError("Invalid channel name or measurement")
    return float(t),{k:float(v) for k,v in values.items()}

def capture(port,seconds,protocol="TCP",cancelled=lambda:False):
    if not 1024<=port<=65535 or not 1<=seconds<=120 or protocol not in ("TCP","UDP"):raise ValueError("Invalid capture settings")
    deadline=time.monotonic()+seconds;times=[];rows=[];names=None;rejected=0
    def append(raw):
        nonlocal names,rejected
        try:
            t,v=parse_frame(raw)
            if names is None:names=sorted(v)
            if sorted(v)!=names or times and t<=times[-1]:raise ValueError("Schema or time changed")
            if len(rows)>=MAX_ROWS or (len(rows)+1)*len(names)>MAX_VALUES:return False
            times.append(t);rows.append([v[k] for k in names]);return True
        except ValueError:rejected+=1;return True
    def active():return time.monotonic()<deadline and not cancelled()
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM if protocol=="TCP" else socket.SOCK_DGRAM) as server:
        server.bind(("127.0.0.1",port));server.settimeout(.2)
        if protocol=="TCP":
            server.listen(1)
            while active():
                try:conn,_=server.accept();break
                except socket.timeout:continue
            else:raise ValueError("No TCP connection received")
            with conn:
                conn.settimeout(.2);buf=b"";keep=True
                while active() and keep:
                    try:data=conn.recv(4096)
                    except socket.timeout:continue
                    if not data:break
                    buf+=data
                    while b"\n" in buf:
                        line,buf=buf.split(b"\n",1);keep=append(line)
                        if not keep:break
                    if len(buf)>MAX_FRAME:raise ValueError("Oversized TCP frame; connection closed")
        else:
            while active():
                try:data,_=server.recvfrom(65535)
                except socket.timeout:continue
                if not append(data):break
    if cancelled():raise InterruptedError("Cancelled")
    if not rows:raise ValueError("No valid measurements received")
    t=np.array(times,dtype=float);y=np.array(rows,dtype=float)
    clock=f"loopback:{protocol}:{port}:{time.time_ns()}"
    channels=[Channel(k,y[:,i],t,"","s",{"time_source":"LabVIEW supplied seconds","clock_id":clock}) for i,k in enumerate(names)]
    return channels,rejected
