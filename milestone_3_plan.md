1.
How will you coordinate your work?

•
Who will coordinate the work?

•
What will their project management practices be?

•
Will you have meetings? How frequently? Who plans their agendas?

2.
What tools will you use to communicate?

•
For each, articulate the alternatives and why that is the best choice.

3.
Who will own component in your architecture?

•
Owning them means being responsible for writing them and making sure they are functional and correct.

•
For each component, list the one person who is in charge of getting it done.

4.
What is your timeline?

•
Include a list of milestones you'll reach and deadlines for each.

5.
How will you verify that you've met your requirements?

•
For each requirement in your requirements document, detail how you will verify it, and if you won't verify it, justify why you won't. This is called an acceptance testing plan.

•
If you propose to write a tests, what exact tests will you conduct and what will count as each test passing?

•
If you propose to conduct reviews or inspections, how will you analyze the code?

•
If you write a proof, what property will you prove?

•
If you conduct a review or inspection, what aspects of the code will you inspect to verify the requirement is met?

•
For all of the requirements, how will your verifications be integrated into your process? Will you run automated tests after every build? Before every commit? When will you conduct inspections and who will be involved?

For each answer you provide, provide a written justification that explains the rationale behind your decisions, given what you know about what you need to build. I want to incentivize you to think deeply about each of these choices, to make sure your process decision actually makes sense.

To make a good plan, brainstorm disasters that might happen and test your plan against them. Illness, injury, API limitations, difficult to fix bugs: how resilient is your plan to all of these crises?

Approach
Developers lead

Items 1-3 above should be relatively straightforward. Devising a set of milestones and indicating a clear verification plan, however, is more difficult. A significant component is your approach to testing. Describe your testing plan in reasonable detail. From an implementation perspective, you may not have the time to build out all the features that you listed and you should prioritize your design effort with a focus on building a minimum viable product. How you prioritize features and integrate this prioritization into your plan matters.
