# Project Goals
I have sample output from a PET reading software. It includes...
    -numbered findings (e.g. Finding 1, Finding 2...). 
        -Each finding can have mutliple time points associated with it. 
        -Each Finding corresponds to a lesion (e.g. lymph node, liver lesion, pulmonary nodule)
        -There are often orthogonal meausrements listed as RECIST Long and RECIST Short, the long and short axis measurements.
        -If there are two or more dates corrresponding to one finding (i.e. the same lymph node or liver lesion at two different time points), the dates will appear in yyyy-mm-dd format.
        -Sometimes there are name collisions, which result in no data being included. Only fields with active findings matter. Examples:
            2022-12-12
                Finding 2 - SUV Sphere
                    Max: 
                    Mean: 
                    Slice with Max: 
                Finding 3 - SUV Sphere (Name Collision)
                    : Name collision prevented result
            2025-06-13
                Finding 2 - SUV Sphere
                    Max: 2.69 SUVbw
                    Mean: 2.2 SUVbw
                    Slice with Max: 133 #
                Finding 3 - SUV Sphere (Name Collision)
                    : Name collision prevented result
            -In the above example, the Max:, Mean:, and Slice with Max: don't have numbers or measurements following them, so they should be cleaned off the inputs. If a date has nothing associated with it, the date should remain, but it should be clear there was no data from that date.
        -Mean SUV doesn't matter in this context and should be cleaned from the input.
        -"Max SUV", "Slice with Max", "RECIST Long", and "RECIST short" and their corresponding dates should be passed into the program.
    
GOALS:
    - Clean pasted plain text, retaining only relevant time, Max SUV, Slice with Max (SUV), long axis, and short axis measurements if these data are there.
    - If long and short axis data are  not there, ignore them.
    - If long and short axis data is there, compare one date to another.
    -Format for SUV Comparison. "Finding X (axia image {slice with Max}). Max SUV {max SUV latest} from {max SUV prior}." 
        - X = finding number 
        - max SUV latest = max suv at the data closest to today.
        - max SUV prior = max suv at the date next closest to today. 
        - slice with max = slice with the highest SUV
    - Format for measurement and SUV comparison: "Finding X. {RECIST long latest} x {RECIST short latest} cm (axial image {blank}) from {RECIST long prior} x {RECIST short prior}. Max SUV {max SUV latest} from {max SUV prior}."
        - Similar to above, where "latest" means the date second closest to today's date.
        - blank = leave a blank space
    - All measurements should be rounded to one decimal place (nearest tenth).

# Sample pasted input
Finding 3

    yyyy-mm-dd
        Finding 3 - SUV Sphere (Name Collision)
            : Name collision prevented result
        Finding 3 - 2D Measure
            RECIST Long: 1.38 cm
            RECIST Short: 1.13 cm
    yyyy-mm-dd
        Finding 3 - SUV Sphere (Name Collision)
            : Name collision prevented result
        Finding 3 - 2D Measure
            RECIST Long: 1.13 cm
            RECIST Short: 0.89 cm



Finding 4

    yyyy-mm-dd
        Finding 4 - SUV Sphere
            Max: 2.29 SUVbw
            Mean: 1.7 SUVbw
            Slice with Max: 162 #
        Finding 4 SUV Sphere
            Max: 
            Mean: 
            Slice with Max: 
        Finding 4 - 2D Measure 1
            RECIST Long: 1.59 cm
            RECIST Short: 1.01 cm
        Finding 4 - 2D Measure 2
            RECIST Long: 
            RECIST Short: 
    yyyy-mm-dd
        Finding 4 - SUV Sphere
            Max: 
            Mean: 
            Slice with Max: 
        Finding 4 SUV Sphere
            Max: 1.45 SUVbw
            Mean: 1.17 SUVbw
            Slice with Max: 166 #
        Finding 4 - 2D Measure 1
            RECIST Long: 
            RECIST Short: 
        Finding 4 - 2D Measure 2
            RECIST Long: 0.92 cm
            RECIST Short: 0.67 cm


# Tools - to be answered
What tools should I use? HTML and JS, python, another? 
I need access to this program at work but would prefer a local execution for privacy.
What other instructions should I include as a best practice?

Questions to answer:
1. Specify the preferred programming language and interface (CLI, GUI, web).
2. Clarify input and output methods (paste, file, terminal, GUI).
3. State any restrictions on dependencies or required libraries.
4. Indicate if automated tests are required.
5. Note if the tool should be cross-platform or Linux-only.

Answers:
Python GUI: I’ll use PySimpleGUI for simplicity and cross-platform support.
Input: Paste-only (text box).
Output: Displayed in the GUI, saved to a text file, and copied to clipboard.
Dependencies: PySimpleGUI, pyperclip (for clipboard), and standard libraries.
Automated tests: I’ll include unit tests for the core parsing/formatting logic.

# Prompts.
If there are questions I've overlooked, or information that's missing, prompt me with questions until the questions are answered.
Suggest lines to add to the Instruction.md to document the information but don't edit this file directly.

# Instructions for workflow.
Make the program as modular as possible.
Check first if functions or classes will compile.
Fix errors if a function or class doesn't compile.
Test the program as a whole.
Are outputs formatted as expected? Prompt me to check and see what needs to be fixed.
Continue until I say the output looks right.
Create a separate README_project.md at the end, describing the program. Make sure to include folder structure if there is any.
Include dependancies in dependancies.txt
