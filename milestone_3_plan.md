
#### How will you coordinate your work?

**Who will coordinate the work?**

The Project Manager (PM), Joe, will coordinate the team's development activities, track progress, and ensure project milestones are met on schedule.

Each developer will implement and test their assigned components. The PM will monitor progress and help resolve problems that affect multiple components.

Justification: Since LightMap consists of several interconnected components, having one person coordinate development will help prevent scheduling conflicts, duplicated work, and integration problems.

**What will their project management practices be?**

We can use tools like GitHub Issues to organize and track development tasks. Each task will include a description, assigned developer, expected completion date, and acceptance criteria.

Tasks will be organized like:
- Todo: Tasks that have not been started.
- In Progress: Tasks currently being implemented.
- In Review: Completed tasks awaiting testing or code review.
- Done: Tasks that have been tested, reviewed, and merged.

**Will you have meetings? How frequently? Who plans their agendas?**

We will hold one weekly meeting, lasting approximately 30 minutes, to discuss development progress.

The PM will prepare the meeting agenda, which will cover:
- Progress made since the previous meeting.
- Current problems or technical difficulties.
- Integration and testing results.
- Tasks and deadlines for the following week.

We will also communicate asynchronously throughout the week whenever problems or questions arise.

If an urgent issue affects the project timeline, the PM may organize an additional short meeting.

2.
**What tools will you use to communicate?**
  
|tool | purpose | |
| --- | --- | --- |
| Discord & Instagram | Daily communication, questions, and voice meetings | Compared with email, Discord and Instagram allow faster discussions and easier communication among multiple group members. |
| GitHub Issues & Instagram | Task assignment, progress tracking, and bug reporting | Compared with separate applications such as Trello, GitHub Issues keeps tasks directly connected to the repository. While Instagram gives group members efficient communication and progress tracking. |
| GitHub Pull Requests | Code reviews and discussions about implementation | Pull requests allow team members to examine specific code changes and provide feedback before merging.| 
| GitHub Repository | Sharing code, documentation, and development progress| Git provides version history and makes it possible to work on separate branches without overwriting other developers' changes. |

3.
Who will own component in your architecture?

| Component |Responsible developer | Responsibilities |
| --- | ---| ---|
| AppModel | Kevin | Maintain application state, capture status, processing settings, and the latest output colour. |
| AppController | Kevin | Handle user actions and coordinate communication between the application components. |
| ControlView| Robert | Implement controls for starting/stopping capture, enabling/disabling the overlay, and displaying status or errors.|
| OverlayView | Lucas | Display the output colour and manage overlay visibility. |
| AudioCapture | Robert | Capture audio from the computer's default output device and manage audio capture sessions.|
| FrequencyAnalyser | Joe | Process audio samples using the Hann window function and Fast Fourier Transform (FFT).|
| ColorMapper | Taj | Convert frequency-magnitude pairs into colours using image-based colour maps and calculate the final RGB colour.|

•
Owning them means being responsible for writing them and making sure they are functional and correct.

•
For each component, list the one person who is in charge of getting it done.

4.
What is your timeline?

Finish modules:
AppModel - 18th
ControlView - 18th
OverlayView - 19th
AppController - 20th
AudioCapture - 20th
FreqAnalyser - 20th
ColorMapper - 22nd

Functional by 27th 

5.
How will you verify that you've met your requirements?

test cases

For each requirement in your requirements document, detail how you will verify it, and if you won't verify it, justify why you won't. This is called an acceptance testing plan.

If you propose to write a tests, what exact tests will you conduct and what will count as each test passing?

If you propose to conduct reviews or inspections, how will you analyze the code?

If you write a proof, what property will you prove?

If you conduct a review or inspection, what aspects of the code will you inspect to verify the requirement is met?

For all of the requirements, how will your verifications be integrated into your process? Will you run automated tests after every build? Before every commit? When will you conduct inspections and who will be involved?

For each answer you provide, provide a written justification that explains the rationale behind your decisions, given what you know about what you need to build. I want to incentivize you to think deeply about each of these choices, to make sure your process decision actually makes sense.

To make a good plan, brainstorm disasters that might happen and test your plan against them. Illness, injury, API limitations, difficult to fix bugs: how resilient is your plan to all of these crises?

Approach
Developers lead

Items 1-3 above should be relatively straightforward. Devising a set of milestones and indicating a clear verification plan, however, is more difficult. A significant component is your approach to testing. Describe your testing plan in reasonable detail. From an implementation perspective, you may not have the time to build out all the features that you listed and you should prioritize your design effort with a focus on building a minimum viable product. How you prioritize features and integrate this prioritization into your plan matters.
