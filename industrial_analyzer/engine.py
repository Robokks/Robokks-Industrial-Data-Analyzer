from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import signal, stats

@dataclass
class Channel:
    name: str
    y: np.ndarray
    t: np.ndarray
    unit: str = ''
    time_unit: str = 'sample'

    def __post_init__(self):
        self.y=np.asarray(self.y,dtype=float)
        self.t=np.asarray(self.t,dtype=float)
        if self.y.ndim!=1 or self.t.shape!=self.y.shape or not np.isfinite(self.t).all():
            raise ValueError("Invalid channel arrays")

    def rate(self):
        d=np.diff(self.t)
        if self.time_unit!='s' or not len(d) or not np.all(d>0) or not np.allclose(d,d[0],rtol=1e-3,atol=1e-12):
            raise ValueError('A uniform, increasing time base in seconds is required.')
        return 1/d[0]

def load(path, sheet=0, delimiter=None, time_column=None, sample_rate=None, header=0):
    p=Path(path); out=[]
    if p.suffix.lower() not in (".tdms",".csv",".txt",".xlsx",".xlsm",".xls"): raise ValueError("Unsupported file extension")
    if sample_rate is not None and (not np.isfinite(sample_rate) or sample_rate<=0): raise ValueError("Invalid sample rate")
    if p.suffix.lower()=='.tdms':
        from nptdms import TdmsFile
        with TdmsFile.open(p) as f:
            for g in f.groups():
                for c in g.channels():
                    y=np.asarray(c[:]);
                    if y.dtype.kind not in 'biuf': continue
                    try: t=c.time_track(); u='s'
                    except (KeyError, ValueError): t=np.arange(len(y)); u='sample'
                    out.append(Channel(f'{g.name}/{c.name}',y.astype(float),t,str(c.properties.get('unit_string','')),u))
        return out
    if p.suffix.lower() in ('.xlsx','.xls','.xlsm'): df=pd.read_excel(p,sheet_name=sheet,header=header)
    else: df=pd.read_csv(p,sep=delimiter or None,engine='python',header=header)
    t=np.arange(len(df),dtype=float); u='sample'
    if sample_rate:
        if sample_rate<=0: raise ValueError('Sample rate must be positive')
        t/=sample_rate; u='s'
    if time_column:
        v=df.pop(time_column); n=pd.to_numeric(v,errors='coerce')
        if n.notna().all(): t=n.to_numpy(float)
        else:
            dt=pd.to_datetime(v,errors='raise'); t=(dt-dt.iloc[0]).dt.total_seconds().to_numpy()
        if not np.isfinite(t).all() or np.any(np.diff(t)<=0): raise ValueError('Time must increase strictly')
        u='s'
    for k in df:
        v=pd.to_numeric(df[k],errors='coerce').to_numpy(float)
        if np.isfinite(v).any(): out.append(Channel(str(k),v,t,time_unit=u))
    return out

def demo():
    rng=np.random.default_rng(42); t=np.arange(600)/10
    return [Channel(f'Parameter {i:03}',50+10*np.sin(t*(.1+i*.013))+rng.normal(0,1+i%4,len(t)),t.copy(),'','s') for i in range(100)]

def describe(y):
    a=y[np.isfinite(y)]
    if not len(a): return {'Valid':0,'Missing':len(y)}
    q=np.percentile(a,[1,5,25,50,75,95,99]); sd=np.std(a,ddof=1) if len(a)>1 else np.nan
    return dict(Valid=len(a),Missing=len(y)-len(a),Min=a.min(),Max=a.max(),Mean=a.mean(),Median=q[3],RMS=np.sqrt(np.mean(a*a)),**{'Std Dev':sd,'Peak-to-Peak':np.ptp(a),'Variance':sd**2,'P01':q[0],'P05':q[1],'Q1':q[2],'Q3':q[4],'P95':q[5],'P99':q[6],'IQR':q[4]-q[2],'Skewness':stats.skew(a) if sd>0 else np.nan,'Excess kurtosis':stats.kurtosis(a) if sd>0 else np.nan})

def paired(a,b):
    if a.time_unit!=b.time_unit or len(a.t)!=len(b.t) or not np.allclose(a.t,b.t,rtol=0,atol=1e-8): raise ValueError('Channels require matching time bases; automatic resampling is disabled.')
    return a.y,b.y

def events(t,mask):
    edges=np.diff(np.r_[False,mask,False].astype(int)); return [(i,j-1,t[i],t[j-1],t[j-1]-t[i]) for i,j in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1))]

def analyze(tool,a,b=None,p=3,q=75,r=50):
    y=a.y; t=a.t; good=np.isfinite(y); v=y[good]; d=describe(y); curves=[]; rows=[]; metrics={}
    def curve(x,z,name): curves.append((x,z,name))
    def raw(): curve(t,y,a.name)
    def table(m): rows.extend(list(m.items()))
    if not np.isfinite([p,q,r]).all(): raise ValueError('Parameters must be finite')
    if tool in ('Frequency Spectrum','Distribution','Statistics','Signal Conditioning','Stability & SPC','Change Detection','Rolling Statistics','Lag & Correlation','Autocorrelation'):
        if p != int(p) or not 1 <= p <= 100000: raise ValueError('Invalid integer window/count')
    if tool in ('Distribution','Statistics') and p>4096: raise ValueError('Maximum 4096 histogram bins')
    if tool=='Lag & Correlation' and (p>1000 or len(y)<3): raise ValueError('Lag requires at least three samples and max lag <= 1000')
    if tool in ('Anomaly Detection','Quality & Outliers','Data Quality','Transients','Envelope & Peaks') and p<=0: raise ValueError('Threshold must be positive')
    if tool in ('Transients','Signal Conditioning') and (tool=='Transients' or q) and np.any(np.diff(t)<=0): raise ValueError('Derivative requires increasing time')
    if not len(v): raise ValueError('No finite samples')
    if tool in ('Frequency Spectrum','Band Energy'):
        fs=a.rate(); n=min(len(y),int(p)) if tool=='Frequency Spectrum' else len(y)
        if n<3 or not np.isfinite(y[:n]).all(): raise ValueError('FFT requires at least three contiguous finite samples')
        z=y[:n]-np.mean(y[:n]); w=np.hanning(n) if q else np.ones(n); f=np.fft.rfftfreq(n,1/fs); amp=2*np.abs(np.fft.rfft(z*w))/w.sum(); amp[0]/=2
        if n%2==0: amp[-1]/=2
        curve(f,amp,'Amplitude'); metrics={'Sample rate Hz':fs,'Peak Hz':f[np.argmax(amp)],'Peak amplitude':amp.max()}
        if tool=='Band Energy':
            f,psd=signal.periodogram(y,fs=fs,detrend='constant'); split=p
            if not 0<split<fs/2: raise ValueError('Band split must lie below Nyquist')
            e=psd*(f[1]-f[0]); rows=[('Below split',e[f<split].sum()),('Above split',e[f>=split].sum())]
    elif tool in ('Distribution','Statistics'):
        h,x=np.histogram(v,bins=max(2,int(p))); curve((x[1:]+x[:-1])/2,h,'Histogram'); sv=np.sort(v); curve(sv,np.arange(1,len(v)+1)/len(v),'CDF'); table(d); metrics={k:d[k] for k in ('Mean','RMS','Std Dev','Median')}
    elif tool in ('Thresholds','Process Capability','State & Events'):
        raw(); low=p; high=q
        if tool=='State & Events':
            mask=good&(y>=p); curve(t,mask.astype(float),'Active state'); rows=[e for e in events(t,mask) if e[-1]>=q]; metrics={'Events':len(rows),'Active samples':mask.sum()}
        else:
            if low>=high: raise ValueError('Lower limit must be less than upper limit')
            curve(t,np.full(len(y),low),'Lower'); curve(t,np.full(len(y),high),'Upper'); masks=[good&(y<low),good&(y>high)]
            for side,m in zip(('Low','High'),masks): rows.extend([(side,*e) for e in events(t,m)])
            metrics={'Below':masks[0].sum(),'Above':masks[1].sum(),'Within %':100*(1-(masks[0]|masks[1]).sum()/len(v))}
            if tool=='Process Capability':
                sd=d['Std Dev']; mu=d['Mean']; metrics.update(Cp=(high-low)/(6*sd) if sd>0 else np.nan,Cpk=min(high-mu,mu-low)/(3*sd) if sd>0 else np.nan); curve(t,np.full(len(y),r),'Target')
    elif tool in ('Comparison','Relationships','Lag & Correlation'):
        x,z=paired(a,b)
        if tool=='Lag & Correlation':
            lags=np.arange(-min(int(p),len(x)-2),min(int(p),len(x)-2)+1); vals=[]
            for lag in lags:
                xx=x[:len(x)-lag] if lag>=0 else x[-lag:]; zz=z[lag:] if lag>=0 else z[:len(z)+lag]; m=np.isfinite(xx)&np.isfinite(zz); vals.append(np.corrcoef(xx[m],zz[m])[0,1] if m.sum()>1 and np.ptp(xx[m])>0 and np.ptp(zz[m])>0 else np.nan)
            vals=np.array(vals); curve(lags,vals,'Pearson r'); 
            if not np.isfinite(vals).any(): raise ValueError("No valid lag correlation")
            i=np.nanargmax(abs(vals)); metrics={'Best lag':lags[i],'Correlation':vals[i]}; rows=list(zip(lags,vals))
        else:
            m=np.isfinite(x)&np.isfinite(z); xx=x[m]; zz=z[m]; 
            if len(xx)<2 or np.ptp(xx)==0: raise ValueError("Regression requires two distinct reference values")
            fit=stats.linregress(xx,zz); metrics={'Pearson r':fit.rvalue,'Slope':fit.slope,'Intercept':fit.intercept,'R squared':fit.rvalue**2}
            if tool=='Comparison': raw(); curve(t,z,b.name)
            else: order=np.argsort(xx); curve(xx,zz,'XY'); curve(xx[order],fit.intercept+fit.slope*xx[order],'Regression')
            rows=list(zip(xx,zz,zz-(fit.intercept+fit.slope*xx)))
    elif tool in ('Signal Conditioning','Stability & SPC','Change Detection','Rolling Statistics'):
        raw(); w=max(2,int(p)); s=pd.Series(y); mean=s.rolling(w,min_periods=w).mean().to_numpy(); sd=s.rolling(w,min_periods=w).std().to_numpy(); curve(t,mean,'Rolling mean'); curve(t,sd,'Rolling std')
        if tool=='Stability & SPC':
            mu=d['Mean']; sigma=d['Std Dev']; lo=mu-q*sigma; hi=mu+q*sigma; curve(t,np.full(len(y),lo),'LCL'); curve(t,np.full(len(y),hi),'UCL'); rows=list(zip(t[(y<lo)|(y>hi)],y[(y<lo)|(y>hi)])); metrics={'Center':mu,'LCL':lo,'UCL':hi}
        elif tool=='Change Detection':
            delta=mean-pd.Series(mean).shift(w).to_numpy(); curve(t,delta,'Baseline shift'); mask=np.abs(delta)>q; rows=list(zip(t[mask],delta[mask])); metrics={'Candidates':mask.sum()}
        elif tool=='Signal Conditioning' and q:
            der=np.r_[np.nan,np.diff(y)/np.diff(t)]; curve(t,der,'Derivative')
    elif tool in ('Anomaly Detection','Quality & Outliers','Data Quality','Transients','Envelope & Peaks'):
        raw(); mask=np.zeros(len(y),bool)
        if tool=='Anomaly Detection': mask=np.abs(y-d['Mean'])>p*d['Std Dev']
        elif tool=='Quality & Outliers': mask=(y<d['Q1']-p*d['IQR'])|(y>d['Q3']+p*d['IQR'])
        elif tool=='Data Quality':
            mask=~good; dt=np.diff(t); metrics={'Missing':mask.sum(),'Duplicate/nonincreasing time':(dt<=0).sum(),'Timing gaps':(dt>p*np.median(dt)).sum() if len(dt) else 0}
        elif tool=='Transients':
            der=np.r_[np.nan,np.diff(y)/np.diff(t)]; curve(t,der,'Slew'); mask=np.abs(der)>p
        else:
            if not good.all(): raise ValueError('Envelope requires finite samples')
            env=np.abs(signal.hilbert(y-np.mean(y))); curve(t,env,'Envelope'); peaks,_=signal.find_peaks(y,prominence=p); mask[peaks]=True
        curve(t[mask],y[mask],'Flags'); rows=list(zip(np.flatnonzero(mask),t[mask],y[mask])); metrics['Flagged samples']=mask.sum()
    elif tool=='Autocorrelation':
        if not good.all(): raise ValueError('Autocorrelation requires finite samples')
        z=y-y.mean(); c=signal.correlate(z,z,method='fft')[len(z)-1:]; c=c/c[0] if c[0]>0 else np.full(len(z),np.nan); n=min(len(c),int(p)+1); curve(np.arange(n),c[:n],'Autocorrelation'); rows=list(enumerate(c[:n]))
    elif tool=='Segment Comparison':
        raw(); m=len(y)//2; d1=describe(y[:m]); d2=describe(y[m:]); rows=[(k,d1[k],d2[k]) for k in d1.keys()&d2.keys()]
    else: raise ValueError(tool)
    return curves,metrics,rows
