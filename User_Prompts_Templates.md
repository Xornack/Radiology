Sources
https://medium.com/@christoph_27312/how-to-code-with-ai-5ef022ebfd4d
I also included some questions copilot asked me but I didn't include in my first iteration of instructions.

# Idea
## Idea
Found in idea.md.

# Specifications
## Objective
Create a step-by-step specification for the given idea in idea.md that can be handed off to developers.
The specification should be saved in specification.md and include the following sections:

- Overview: A concise summary of the idea or feature.
- Goals: The main objectives.
- Requirements: Detailed functional and non-functional requirements.
- Assumptions: All assumptions made while drafting the spec (to be validated or refined later).
- Open Questions: Points needing further clarification or decisions.
- Step-by-Step Plan: A high-level roadmap of implementation steps.

## Instructions
Incorporate any background or context specific to the project. Append or refine assumptions as needed.
Keep the structure modular, so any section can be easily updated by subsequent prompts.
Once the spec is generated, allow for iterative refinements in each section. Create any folder or file as seems appropriate.
Create dependancies.txt for a list of the dependancies.

## Request
Generate an initial draft of specification.md based on the above structure.
Make sure each requirement or assumption is clearly stated.
Ensure the plan is broken down into logical, actionable steps.

Ask as many questions as are needed to accomplish the above specificatoins.md.
Let's systematically review each Open Question for the spec one by one.

## Open Question
• Restate the first unresolved question in your own words.  
• Offer potential answers.
• Ask if we should confirm it, provide more details, or revise it.

*(Stop here and wait for user input)*

After receiving your input:
1. Update the appropriate section in the specification (Requirements, Assumptions, etc.) with the resolved information
2. Mark the question as resolved in the Open Questions section
3. Immediately continue to the next unresolved question, following the same process

Continue this cycle until all Open Questions are resolved.

### Example workflow:
1. Present Question 1 and wait for input
2. After receiving input:
   - Add details to Requirements section
   - Mark Question 1 as resolved
3. Present Question 2 and wait for input
4. And so on...

## Verify Specification
Review the updated specification.md and compare it with idea.md to confirm they remain aligned.
Identify any unanswered questions or clarifications needed before we begin implementation,
and list them as an "Open Questions" snippet so they can be added to the file if necessary.

If this leads to some important open questions, go back to Step 3: Open Questions

Add any section or text to specifications.md that might help a developer execute the idea.

# Implementation with Test-Driven Development

Refer to the "Implementation Steps" in specification.md.

## Process:

1. Identify the next incomplete step in `specification.md`. If none are marked as completed, start at step 1.

2. For each implementation step:
   - First, write tests for the functionality where applicable (following test-driven development principles)
   - Implement the required code or updates to make the tests pass
   - Run the tests to verify the implementation works as expected
   - Include test results in your response

3. When a step is successfully implemented and verified with tests:
   - Mark the step as completed in `specification.md`
   - Report the test results and any observations
   - If there is a verifiable output (string, int, float...etc), ask if the output looks correct and check if it is    correctly formatted and the type is correct.

4. If all steps are completed, respond that no more steps remain.

After each implementation, run the tests and report results to confirm functionality works as expected.

If the program is functioning as expected, create a README.txt using best practices to explain the program.
