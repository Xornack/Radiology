# Enhanced Specification Creation Prompt

## Objective
Create a step-by-step specification for the given idea in idea.md that can be handed off to developers. The specification should be saved in specification.md and include the following sections:

- **Overview**: A concise summary of the idea or feature.
- **Goals**: The main objectives.
- **Requirements**: Detailed functional and non-functional requirements.
- **Assumptions**: All assumptions made while drafting the specifications (to be validated or refined later).
- **Open Questions**: Points needing further clarification or decisions.
- **Step-by-Step Plan**: A high-level roadmap of implementation steps.

## Technical Context
Before starting, gather information about:
- Target deployment environment (browser capabilities, IT restrictions)
- Expected data volumes (file counts, sizes, processing frequency)
- User technical expertise level
- Integration requirements with existing systems
- Performance expectations and constraints

## Stakeholder Analysis
Consider and document:
- Primary users and their workflows
- IT administrators and security requirements  
- Developers who will implement the solution
- End-user support and training needs
- Compliance and regulatory considerations (especially for medical applications)

## Instructions
Incorporate any background or context specific to the project. Append or refine assumptions as needed. Keep the structure modular, so any section can be easily updated by subsequent prompts. Once the spec is generated, allow for iterative refinements in each section. Create any folder or file as seems appropriate. Create dependencies.txt for a list of the dependencies.

## Request
Generate an initial draft of specification.md based on the above structure. Make sure each requirement or assumption is clearly stated. Ensure the plan is broken down into logical, actionable steps.

## Open Questions Methodology
Ask as many questions as are needed to accomplish the above specification.md. Let's systematically review each Open Question for the spec one by one.

For each open question:
• **Present 2-4 concrete options** with pros/cons
• **Include implementation complexity estimates**
• **Suggest a recommended approach** with rationale
• **Ask for user preference** with follow-up clarifying questions
• **Update specification immediately** after each resolution
• **Validate that the resolution** doesn't conflict with previous decisions

### Open Question Process
• Restate the first unresolved question in your own words.
• Offer potential answers with detailed analysis.
• Ask if we should confirm it, provide more details, or revise it.

(Stop here and wait for user input)

After receiving your input:
- Add details to Requirements section
- Mark the question as resolved in the Open Questions section
- **Verify alignment** with original idea.md requirements
- **Check for conflicts** with existing assumptions
- **Update related** functional/technical requirements
- **Ensure success criteria** are still achievable
- **Document any scope changes** or trade-offs made
- Immediately continue to the next unresolved question, following the same process

Continue this cycle until all Open Questions are resolved.

### Example workflow:
1. Present Question 1 and wait for input
2. After receiving input:
   - Add details to Requirements section
   - Mark Question 1 as resolved
   - Validate alignment and update related sections
3. Present Question 2 and wait for input
4. And so on...

## Risk Assessment
For each major technical decision, document:
- Implementation risks and mitigation strategies
- Browser compatibility risks
- Performance bottlenecks and scaling limitations
- Security considerations
- Fallback options if primary approach fails

## Requirements Validation
After resolving each open question:
- Verify alignment with original idea.md requirements
- Check for conflicts with existing assumptions
- Update related functional/technical requirements
- Ensure success criteria are still achievable
- Document any scope changes or trade-offs made

## Verify Specification
Review the updated specification.md and compare it with idea.md to confirm they remain aligned. Identify any unanswered questions or clarifications needed before we begin implementation, and list them as an "Open Questions" snippet so they can be added to the file if necessary.

If this leads to some important open questions, go back to Step 3: Open Questions

Add any section or text to specification.md that might help a developer execute the idea.

## Implementation Readiness Check
Before finalizing specification:
- Verify all dependencies are clearly documented
- Confirm technical feasibility of chosen approaches
- Validate that requirements are testable and measurable
- Ensure handoff documentation is complete
- Check that specification supports iterative development
- Document decision rationale for future reference

## Documentation Management
- Commit specification at major milestones
- Use descriptive commit messages documenting decisions made
- Tag versions when moving between phases
- Include change log for requirement updates
- Document decision rationale for future reference

## Enhanced Requirements Traceability
Ensure that:
- Each requirement has a clear identifier (FR001, NFR001, TR001, etc.)
- Requirements are grouped logically (Functional, Non-Functional, Technical)
- Dependencies between requirements are documented
- Each requirement is testable and measurable
- Success criteria map back to specific requirements

## Quality Assurance Checklist
Before considering the specification complete:

### Completeness
- [ ] All sections are filled out with adequate detail
- [ ] All open questions have been resolved
- [ ] Dependencies are comprehensively documented
- [ ] Implementation plan has clear, actionable steps

### Consistency
- [ ] Requirements don't contradict each other
- [ ] Assumptions are realistic and validated
- [ ] Technical choices align with constraints
- [ ] Success criteria are achievable with given resources

### Clarity
- [ ] Requirements are unambiguous
- [ ] Technical terms are defined or explained
- [ ] Implementation steps are logical and sequential
- [ ] Handoff documentation is complete

### Technical Feasibility
- [ ] Chosen technologies are appropriate for the problem
- [ ] Performance requirements are realistic
- [ ] Security and compliance needs are addressed
- [ ] Fallback options are viable

## Output Files
The process should generate:
1. **specification.md** - Complete technical specification
2. **dependencies.txt** - Comprehensive dependency list
3. **Any additional files** deemed necessary for implementation

## Success Criteria for This Process
- Specification is ready for immediate developer handoff
- All technical decisions are documented with rationale
- Requirements are complete, consistent, and testable
- Implementation plan is clear and actionable
- Risk mitigation strategies are in place
- Future enhancement path is documented
