"""Engineering calculations. Full-resolution inputs; explicit units and assumptions."""
import ast
import operator
import numpy as np
from scipy import signal, integrate
from engine import Channel, paired, describe

def finite(x):
    x=np.asarray(x,dtype=float)
    if x.ndim!=1 or len(x)<2 or not np.isfinite(x).all():raise ValueError("At least two finite samples are required")
    return x

def aligned(*channels):
    if not channels:raise ValueError("Select channels")
    for c in channels[1:]:paired(channels[0],c)
    return [finite(c.y) for c in channels]

def mechanical_power(speed,torque):
    rpm,nm=aligned(speed,torque)
    return rpm*nm*(2*np.pi/60000)

def efficiency(power_in,power_out,minimum=.01):
    if not np.isfinite(minimum) or minimum<=0:raise ValueError("Minimum input power must be positive")
    x,y=aligned(power_in,power_out)
    result=np.full_like(x,np.nan);valid=(x>=minimum)&(y>=0)
    np.divide(100*y,x,out=result,where=valid)
    return result

def loss_torque(speed,power_in,power_out,minimum_rpm=1.):
    if not np.isfinite(minimum_rpm) or minimum_rpm<=0:raise ValueError("Minimum speed must be positive")
    rpm,pin,pout=aligned(speed,power_in,power_out)
    result=np.full_like(rpm,np.nan)
    np.divide((pin-pout)*60000,2*np.pi*rpm,out=result,where=np.abs(rpm)>=minimum_rpm)
    return result

def electrical(voltage,current):
    v,i=aligned(voltage,current)
    vr=np.sqrt(np.mean(v*v));ir=np.sqrt(np.mean(i*i));p=np.mean(v*i);s=vr*ir
    return {"Voltage RMS (V)":vr,"Current RMS (A)":ir,"Real power (W)":p,"Apparent power (VA)":s,"True power factor":p/s if s else np.nan},v*i

def three_phase(channels):
    if len(channels)!=6:raise ValueError("Select phase-to-neutral voltage and current for A, B, C")
    aligned(*channels)
    total=0.;apparent=0.;curves=[];m={}
    for phase,j in zip("ABC",range(0,6,2)):
        x,p=electrical(*channels[j:j+2]);total+=x["Real power (W)"];apparent+=x["Apparent power (VA)"];curves.append(p)
        m.update({f"{phase} {k}":v for k,v in x.items()})
    m.update({"Total real power (W)":total,"Sum phase VA":apparent,"Aggregate PF (P/sum VA)":total/apparent if apparent else np.nan})
    return m,np.sum(curves,axis=0)

def harmonic_metrics(c,fundamental,max_harmonic=20):
    y=finite(c.y);fs=c.rate()
    if not 0<fundamental<fs/2 or max_harmonic<2:raise ValueError("Invalid fundamental or harmonic count")
    # Simultaneous least-squares harmonic fit; avoids leakage from noninteger FFT bins.
    n=min(int(max_harmonic),int(np.ceil(fs/(2*fundamental)))-1,50)
    if n<2 or len(y)<2*n+1 or (c.t[-1]-c.t[0])*fundamental<2:raise ValueError("Insufficient samples/cycles for harmonic analysis")
    t=c.t-c.t[0];cols=[np.ones(len(y))]
    if len(y)*(2*n+1)>10_000_000:raise ValueError("Choose a smaller interval for harmonic fit")
    for k in range(1,n+1):
        phase=2*np.pi*k*fundamental*t;cols.extend((np.sin(phase),np.cos(phase)))
    fit,_,rank,_=np.linalg.lstsq(np.column_stack(cols),y,rcond=None)
    if rank!=len(cols):raise ValueError("Harmonic fit is rank deficient")
    rms=np.hypot(fit[1::2],fit[2::2])/np.sqrt(2)
    thd=np.linalg.norm(rms[1:])/rms[0]*100 if rms[0]>np.finfo(float).eps*max(1.,np.max(np.abs(y))) else np.nan
    return np.arange(1,n+1)*fundamental,rms,{"Fundamental RMS":rms[0],"THD (% of fundamental)":thd,"Harmonics evaluated":n}

def filter_signal(c,cutoff,kind="lowpass",order=4):
    y=finite(c.y);fs=c.rate()
    if kind not in ("lowpass","highpass") or not 0<cutoff<fs/2 or not 1<=int(order)<=8:raise ValueError("Invalid filter cutoff/order")
    sos=signal.butter(int(order),cutoff,btype=kind,fs=fs,output="sos")
    return signal.sosfiltfilt(sos,y)

def integrate_signal(c):
    y=finite(c.y);c.rate()
    return integrate.cumulative_trapezoid(y,c.t,initial=0.)

def differentiate(c):
    y=finite(c.y);c.rate();return np.gradient(y,c.t)

def envelope_spectrum(c,low,high):
    y=finite(c.y);fs=c.rate()
    if not 0<low<high<fs/2:raise ValueError("Select a valid resonance band below Nyquist")
    sos=signal.butter(4,[low,high],btype="bandpass",fs=fs,output="sos")
    env=np.abs(signal.hilbert(signal.sosfiltfilt(sos,y)))
    f,psd=signal.periodogram(env,fs=fs,window="hann",detrend="constant")
    rms=np.sqrt(np.mean(y*y))
    return f,psd,{"RMS":rms,"Crest factor":np.max(np.abs(y))/rms if rms else np.nan}

def bearing_frequencies(rpm,elements,ball_diameter,pitch_diameter,angle_deg=0):
    if not np.isfinite([rpm,elements,ball_diameter,pitch_diameter,angle_deg]).all() or rpm<=0 or int(elements)!=elements or elements<2 or not 0<ball_diameter<pitch_diameter or not 0<=angle_deg<90:raise ValueError("Invalid bearing geometry or speed")
    fr=rpm/60;ratio=ball_diameter/pitch_diameter;z=ratio*np.cos(np.deg2rad(angle_deg))
    return {"Shaft Hz":fr,"FTF Hz":fr/2*(1-z),"BPFO Hz":elements*fr/2*(1-z),"BPFI Hz":elements*fr/2*(1+z),"BSF Hz":fr/(2*ratio)*(1-z*z)}

def order_spectrum(vibration,speed,samples_per_rev=128):
    y,rpm=aligned(vibration,speed);vibration.rate()
    if np.any(rpm<=0) or not 16<=samples_per_rev<=2048:raise ValueError("Order tracking requires strictly positive shaft speed")
    rev=integrate.cumulative_trapezoid(rpm/60,vibration.t,initial=0.)
    n=int(np.floor(rev[-1]*samples_per_rev))+1
    if not 2*samples_per_rev<=n<=2_000_000:raise ValueError("Need 2 revolutions and at most 2 million angle samples")
    x=np.arange(n)/samples_per_rev
    a=np.interp(x,rev,y);w=np.hanning(n);amp=2*np.abs(np.fft.rfft((a-a.mean())*w))/w.sum();amp[0]/=2
    if n%2==0:amp[-1]/=2
    return np.fft.rfftfreq(n,1/samples_per_rev),amp

def spectrogram(c,nperseg=256):
    y=finite(c.y);fs=c.rate();n=int(nperseg)
    if not 16<=n<=min(len(y),8192):raise ValueError("Invalid spectrogram window")
    if (len(y)//max(1,n//2)+1)*(n//2+1)>4_000_000:raise ValueError("Choose a shorter interval for spectrogram")
    f,t,s=signal.spectrogram(y,fs=fs,nperseg=n,noverlap=n//2,scaling="density")
    return t+c.t[0],f,10*np.log10(np.maximum(s,np.finfo(float).tiny))

def resample(c,rate):
    y=finite(c.y)
    if c.time_unit!="s" or not np.all(np.diff(c.t)>0) or not np.isfinite(rate) or rate<=0:raise ValueError("Resampling requires increasing seconds and a positive rate")
    n=int(np.floor((c.t[-1]-c.t[0])*rate))+1
    if not 2<=n<=2_000_000:raise ValueError("Resampling limited to 2 million points")
    # Explicit linear interpolation. Downsampling is refused to avoid aliasing.
    if rate<1/np.min(np.diff(c.t))*(1-1e-6):raise ValueError("Downsampling requires an anti-alias filter; use a separately validated workflow")
    t=c.t[0]+np.arange(n)/rate
    return Channel(c.name+" resampled",np.interp(t,c.t,y),t,c.unit,"s",dict(c.metadata))

def comparison_metrics(a,b,tolerance):
    if tolerance<0 or not np.isfinite(tolerance):raise ValueError("Tolerance must be nonnegative")
    x,y=aligned(a,b);d=y-x
    return {"Bias (B-A)":np.mean(d),"RMSE":np.sqrt(np.mean(d*d)),"Max absolute error":np.max(np.abs(d)),"Within tolerance (%)":100*np.mean(np.abs(d)<=tolerance),"Paired samples":len(d)},d

OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}
FUNCS={"abs":np.abs,"sqrt":np.sqrt,"sin":np.sin,"cos":np.cos,"log":np.log,"exp":np.exp}
def expression(text,channels):
    """Restricted arithmetic interpreter; no eval, attributes, indexing or arbitrary calls."""
    if len(text)>256 or not channels:raise ValueError("Expression limited to 256 characters")
    arrays=aligned(*channels);env={chr(65+i):x for i,x in enumerate(arrays)}
    try:tree=ast.parse(text,mode="eval")
    except SyntaxError as exc:raise ValueError("Invalid expression") from exc
    if sum(1 for _ in ast.walk(tree))>64:raise ValueError("Expression too complex")
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float) and abs(n.value)<=1e12:return float(n.value)
        if isinstance(n,ast.Name) and n.id in env:return env[n.id]
        if isinstance(n,ast.Name) and n.id=="pi":return np.pi
        if isinstance(n,ast.UnaryOp) and type(n.op) in (ast.UAdd,ast.USub):return visit(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
        if isinstance(n,ast.BinOp) and type(n.op) in OPS:
            if isinstance(n.op,ast.Pow) and (not isinstance(n.right,ast.Constant) or type(n.right.value) not in (int,float) or abs(n.right.value)>8):raise ValueError("Exponent must be a literal between -8 and 8")
            return OPS[type(n.op)](visit(n.left),visit(n.right))
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in FUNCS and len(n.args)==1 and not n.keywords:return FUNCS[n.func.id](visit(n.args[0]))
        raise ValueError("Unsupported expression syntax")
    with np.errstate(all="ignore"):
        result=np.broadcast_to(visit(tree.body),arrays[0].shape).astype(float,copy=True)
    result[~np.isfinite(result)]=np.nan
    return result
