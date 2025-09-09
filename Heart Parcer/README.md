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
3. **Paste** cardiac data into the input text area
4. **Choose processing type**:
   - **TMVR**: For transcatheter mitral valve replacement measurements
   - **LV/RV Function**: For ventricular function analysis
   - **Flow Measurement**: For aortic/pulmonary flow quantification
5. **Process**
6. **Copy or save** the formatted output

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
