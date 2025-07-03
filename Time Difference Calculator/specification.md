# Specification

## Overview
A web-based tool that calculates the time difference between two timestamps, accounting for time zones. This is useful for calculating the time difference between a radiopharmaceutical injection and a PET scan.

## Goals
- Create a user-friendly web interface for time difference calculations.
- Handle time zone differences automatically.
- Provide clear and accurate results.

## Requirements
- The tool will be a web-based interface built with HTML and JavaScript.
- It will accept two timestamps as input via a web form.
- The tool will support different time zones.
- The output will be the time difference in the format "X hours, Y minutes".
- If an invalid timestamp is entered, the tool will display a clear error message.
- It will use standard web technologies with no external libraries.
- Automated tests will be created to ensure accuracy.
- The tool will be accessible through any modern web browser.

## Assumptions
- Users will have a modern web browser with JavaScript enabled.
- Users will input timestamps in a reasonable format (e.g., YYYY-MM-DD HH:MM:SS).

## Open Questions
- **[Resolved]** What is the desired format for the output? (e.g., "HH:MM:SS", "X hours, Y minutes, Z seconds") - *Resolution: "X hours, Y minutes"*
- **[Resolved]** How should the tool handle invalid timestamp formats? - *Resolution: Display a clear error message in the UI.*
- **[Resolved]** Should the tool support daylight saving time? - *Resolution: No, the tool will not support DST.*

## Step-by-Step Plan
1.  **Setup Project Structure**: Create `index.html`, `style.css`, and `app.js`.
2.  **Create HTML Structure**: Design the web page with input fields for timestamps and a button to trigger the calculation.
3.  **Implement Core Logic**: Write the JavaScript code for time difference calculation.
4.  **Handle Time Zones**: Add support for different time zones in JavaScript.
5.  **Add Styling**: Use CSS to style the web interface for a clean and user-friendly look.
6.  **Write Tests**: Develop unit tests for the JavaScript logic.
7.  **Create README**: Write a `README.md` with instructions on how to use the tool.
