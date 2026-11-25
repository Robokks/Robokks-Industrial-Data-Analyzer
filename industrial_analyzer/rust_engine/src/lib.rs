use pyo3::prelude::*;
/// Finite min/max for plotting buckets; preserves narrow excursions.
#[pyfunction]
fn bucket_extrema(values: Vec<f64>, width: usize) -> PyResult<Vec<(usize, f64)>> {
    if width == 0 { return Err(pyo3::exceptions::PyValueError::new_err("width must be positive")); }
    let mut out = Vec::new();
    for (bucket, chunk) in values.chunks(width).enumerate() {
        let mut lo: Option<(usize,f64)> = None;
        let mut hi: Option<(usize,f64)> = None;
        for (i,&v) in chunk.iter().enumerate() {
            if !v.is_finite() { continue; }
            let idx = bucket*width+i;
            if lo.map_or(true, |x| v<x.1) {lo=Some((idx,v));}
            if hi.map_or(true, |x| v>x.1) {hi=Some((idx,v));}
        }
        if let (Some(a),Some(b))=(lo,hi) { if a.0<=b.0 {out.push(a); if a.0!=b.0 {out.push(b);}} else {out.push(b);out.push(a);} }
    }
    Ok(out)
}
#[pymodule]
fn analyzer_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(bucket_extrema,m)?)?; Ok(())
}
