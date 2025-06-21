A program that combines JPEG photos into a single MP4. Other requirements.
1. Runs locally
2. Asks for a folder path
3. In the folder is a list of JPEG photos (stacked photos from a CT, MRI, SPECT, PET, or time-resolves nuclear medicine planar imgages usually) in the order they should be stacked together.
4. Checks to make sure there are pictures present and exits with error code if there aren't.
5. Combines the photos into an MP4.
7. Saves and runs the MP4 to make sure the process worked.

Language and UI, preference in order:
1. Simple javascript program initiated in the browser (HTML)
2. Javascript program is dependancies that can run locall and can be run on my work PC, which has restriction on executables but will allow a brower program.
3. A python program with minimal dependancies. If python, prefer PyQt6 as the GUI.
4. C++, simple GUI
