# Heart Parser (Web)

A comprehensive web-based parser for cardiac MRI and TMVR measurement data, designed to convert raw cardiac imaging software output into standardized radiology report format.

## Features

### 🫀 **TMVR Analysis**
- Parses 2D and 3D transcatheter mitral valve replacement measurements
- Extracts trigone-trigone distance, SL distance, IC distance, area, and perimeter
- Automatic area conversion from cm² to sq mm
- Professional report formatting

### 📊 **LV/RV Function Analysis**
- Complete left and right ventricular function assessment
- Multi-line input format support (handles both inline and separated values)
- Gender-specific clinical assessments based on established reference ranges
- Parameters include:
  - End-diastolic volume (EDV) and indexed values (EDVI)
  - End-systolic volume (ESV) and indexed values (ESVI)
  - Stroke volume (SV) and ejection fraction (EF)
  - Myocardial mass and mass index

### 🩸 **Flow Quantification**
- Aortic and pulmonary artery flow analysis
- Forward/reverse volume measurements
- Regurgitant fraction calculations
- Peak velocity and pressure gradient assessments
- Automatic vessel type detection

### 🧬 **Clinical Intelligence**
- **Gender-specific normal values** based on established clinical studies
- **Comprehensive assessments**: normal, abnormal (low/high), mildly/moderately/severely depressed
- **Reference standards**: Kawel-Boehm JCMR 2015, Salton JACC 2002, Plein JMRI 2003

## Usage

1. **Open** `heart_parser_web.html` in any modern web browser
2. **Select patient gender** from the dropdown menu
3. **Paste** raw cardiac MRI data into the input text area
4. **Choose processing type**:
   - **TMVR**: For transcatheter mitral valve replacement measurements
   - **LV/RV Function**: For ventricular function analysis
   - **Flow Measurement**: For aortic/pulmonary flow quantification
5. **Copy or save** the formatted output

## Clinical Reference Ranges

### Left Ventricle
| Parameter | Male (Normal) | Female (Normal) | Reference |
|-----------|---------------|-----------------|-----------|
| LVEF (%) | 57-77 | 57-77 | Salton JACC 2002, Kawel-Boehm JCMR 2015 |
| LVEDVi (mL/m²) | 57-105 | 56-96 | Kawel-Boehm JCMR 2015 |
| LV Mass Index (g/m²) | 49-85 | 41-81 | Salton JACC 2002 |

### Right Ventricle
| Parameter | Male (Normal) | Female (Normal) | Reference |
|-----------|---------------|-----------------|-----------|
| RVEF (%) | 52-72 | 51-71 | Plein JMRI 2003, Kawel-Boehm JCMR 2015 |
| RVEDVi (mL/m²) | 61-121 | 48-112 | Kawel-Boehm JCMR 2015 |

## Input Format Examples

### TMVR Input
```
at R-R 70%
2D-TT-Distance(s): 22.2 mm
2D-SL-Distance(s): 40.2 mm
2D-IC-Distance(s): 26.8 mm
2D-Area(s): 7.46 cm²
2D-P(s): 110 mm
3D-TT-Distance(s): 22.2 mm
3D-SL-Distance(s): 40.2 mm
3D-IC-Distance(s): 27.2 mm
3D-P(s): 115 mm
```

### LV/RV Function Input
```
SAX3D Stack LV Function
EDV:
72.85 ml
ESV:
26.82 ml
EF:
63.18 %
EDV/BSA:
32.20 ml/m²
Myo Mass/BSA (Diast):
32.19 g/m²

SAX3D Stack RV Function
RVEDV:
81.96 ml
RVEF:
42.73 %
RVEDV/BSA:
36.23 ml/m²
```

### Flow Measurement Input
```
Flow Analysis Aorta
Total Forward Volume:
32.47 ml
Total Backward Volume:
-2.57 ml
Regurgitation Fraction:
7.91 %
Maximum Velocity (1x1 px):
63.10 cm/s
Max Pressure Gradient:
1.59 mmHg
```

## Output Examples

### TMVR Output
```
2D
Trigone-trigone distance: 22.2 mm
SL distance: 40.2 mm
IC distance: 26.8 mm
Area: 746 sq mm
Perimeter: 110 mm

3D:
Trigone-trigone distance: 22.2 mm
SL distance: 40.2 mm
IC distance: 27.2 mm
Perimeter: 115 mm
```

### LV/RV Function Output
```
LEFT VENTRICLE:

Left ventricular end-diastolic volume (LVEDV): 72.8 mL
Left ventricular end-systolic volume (LVESV): 26.8 mL
Left ventricular stroke volume (LVSV): 46.0 mL
Left ventricular ejection fraction (LVEF): 63.2%, normal
Myocardial mass (end-diastole): 72.8 g
Myocardial mass index: 32.2 g/m2, abnormal, low
Left ventricular end-diastolic volume index (LVEDVi): 32.2 mL/m2, normal
Left ventricular end systolic volume index (LVESVi): 11.9 mL/m2

RIGHT VENTRICLE: 

Right ventricular end-diastolic volume (RVEDV): 82.0 mL
Right ventricular end-systolic volume (RVESV): 46.9 mL
Right ventricular stroke volume (RVSV): 35.0 mL
Right ventricular ejection fraction (RVEF): 42.7%, mildly depressed
Right ventricular end-diastolic volume index (RVEDVi): 36.2 mL/m2, normal
Right ventricular end systolic volume index (RVESVi): 20.8 mL/m2
```

### Flow Quantification Output
```
FLOW QUANTIFICATION:
Aorta:
Forward volume: 32.5 mL
Reverse volume: -2.6 mL
Regurgitant fraction: 7.9%
Peak velocity: 63.1 cm/s
Peak gradient: 1.6 mmHg

Pulmonary Artery:
Forward volume: 35.2 mL
Reverse volume: -1.34 mL
Regurgitant fraction: 3.8%
Peak velocity: 67.4 cm/s
Peak gradient: 1.8 mmHg
```

## Technical Features

- **Single HTML file**: No external dependencies, runs entirely in browser
- **Multi-line format support**: Handles various cardiac software output formats
- **Robust parsing**: Handles both inline and separated value formats
- **Clinical validation**: Assessments based on peer-reviewed reference studies
- **Data security**: All processing is local, no data transmission
- **Export functionality**: Copy to clipboard or save as text file

## Browser Compatibility

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

## Medical Disclaimer

This tool is designed to assist with clinical data formatting and should not replace clinical judgment. All results should be reviewed by qualified medical professionals. Reference ranges are based on published studies and may need adjustment for specific patient populations.

## References

1. Kawel-Boehm N, et al. Reference ranges for cardiovascular magnetic resonance measurements in adults and children: a cross-sectional study analysis of published data. J Cardiovasc Magn Reson. 2015;17:29.

2. Salton CJ, et al. Gender differences and normal left ventricular anatomy in an adult population free of hypertension. J Am Coll Cardiol. 2002;39(6):1055-60.

3. Plein S, et al. Normal human left and right ventricular and left atrial dimensions using steady state free precession magnetic resonance imaging. J Magn Reson Imaging. 2003;17(3):323-9.

## License

This project is intended for clinical and educational use in radiology and cardiology practices.
