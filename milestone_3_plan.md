
### How will you coordinate your work?

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

Justification:

**Will you have meetings? How frequently? Who plans their agendas?**

We will hold one weekly meeting, lasting approximately 30 minutes, to discuss development progress.

The PM will prepare the meeting agenda, which will cover:
- Progress made since the previous meeting.
- Current problems or technical difficulties.
- Integration and testing results.
- Tasks and deadlines for the following week.

We will also communicate asynchronously throughout the week whenever problems or questions arise.

If an urgent issue affects the project timeline, the PM may organize an additional short meeting.

Justification: Weekly meetings provide regular opportunities to identify problems and coordinate work without taking too much time away from development. Other asynchronous communication allows smaller problems to be addressed immediately.

### What tools will you use to communicate?
  
|tool | purpose | |
| --- | --- | --- |
| Discord & Instagram | Daily communication, questions, and voice meetings | Compared with email, Discord and Instagram allow faster discussions and easier communication among multiple group members. |
| GitHub Issues & Instagram | Task assignment, progress tracking, and bug reporting | Compared with separate applications such as Trello, GitHub Issues keeps tasks directly connected to the repository. While Instagram gives group members easy communication and progress reporting. |
| GitHub Pull Requests | Code reviews and discussions about implementation | Pull requests allow team members to examine specific code changes and provide feedback before merging.| 
| GitHub Repository | Sharing code, documentation, and development progress| Git provides version history and makes it possible to work on separate branches without overwriting other developers' changes. |

### Who will own component in your architecture?

| Component |Responsible developer | Backup Developer | Responsibilities |
| --- | ---| ---|---|
| AppModel | Kevin | Taj|Maintain application state, capture status, processing settings, and the latest output colour. |
| AppController | Kevin | Joe |Handle user actions and coordinate communication between the application components. |
| ControlView| Robert | Robert |Implement controls for starting/stopping capture, enabling/disabling the overlay, and displaying status or errors.|
| OverlayView | Lucas | Taj |Display the output colour and manage overlay visibility. |
| AudioCapture | Robert | Lucas|Capture audio from the computer's default output device and manage audio capture sessions.|
| FrequencyAnalyser | Joe | Lucas |Process audio samples using the Hann window function and Fast Fourier Transform (FFT).|
| ColorMapper | Taj | Kevin |Convert frequency-magnitude pairs into colours using image-based colour maps and calculate the final RGB colour.|

### What is your timeline?

Finish modules:

- AppModel - 18th

- AudioCapture - 18th

- ControlView - 18th

- OverlayView - 19th

- AppController - 20th

- FreqAnalyser - 20th

- ColorMapper - 22nd

- Functional by 27th 

### How will you verify that you've met your requirements?

Our detailed testing strategy is documented in verification_plan.md, which explains the verification methods for each requirement and the reasoning behind them. The exact test procedures, expected results, and passing criteria are provided in verification_checklist.md.

AppModel -> Review and Inspection

We will all individually review and inspect the code against the SOLID principles 

AudioCapture -> Test Case

Compare audio capture output to existing audio capture software using an external audio comparison software. We will also test audio chunk consistency, start/stop functionality, and resource cleanup.

ControlView -> Test Case

We have to test for when audio start/stops capture, overlay is enabled/disabled, and all statuses with intentional errors thrown. We will write test cases to give us full path coverage of these three functions

OverlayView ->  Test Case

We provide the overlayView with a colour cycling function and we confirm visually if it matches the function we gave

FrequencyAnalyser → Test Cases

Provide audio with a known frequency and evaluate accuracy using percentage error against the expected frequency spectrum.

- Start with 1–2 frequencies.

- Test harmonics and combinations of frequencies.

- Test with actual game audio.

ColorMapper → Test Cases

Provide a frequency-volume map and colour map, then compare the colours produced with the expected output calculated manually.

- Start with grayscale (light-dark only) maps.

- Test colour gradients.

- Finally, test custom colour maps.

AppController → Test Cases

Use mock components to test how AppController handles start/stop requests, capture errors, overlay visibility, and communication between components.

All detailed test cases, including specific inputs, expected outputs, and passing conditions, are listed in verification_checklist.md. The mapping between these tests and our Milestone 2 requirements is provided in verification_plan.md.
  
### How will verification fit into our process?

Our verification process follows the workflow described in verification_plan.md, while verification_checklist.md provides the detailed testing and review procedures used to determine whether each requirement has been satisfied.

| When | What happens | Who |
| --- | --- | --- |
| Before opening a pull request | The owner runs their component's tests locally and records the results using the verification checklist. Manual checks (AudioCapture comparison, OverlayView colour cycle) are done now, with a screenshot or short note as evidence. | Component owner |
| On every push and pull request | Automated tests (ControlView, FrequencyAnalyser, ColorMapper, AppController) run through GitHub Actions. A pull request cannot move to Done unless they pass. | Automatic |
| Before merging | At least one other team member (the backup owner in the table below) reviews the pull request. | Backup owner |
| After every merge to main | The full automated test suite is re-run so a merge that breaks another component is caught immediately. | Automatic |
| Right after AppModel is finished (18th) | All members individually inspect AppModel against the SOLID checklist, then compare findings in a short call. The PM records the results in the Issue. | Whole team, PM schedules |
| Integration window (23rd–26th) | Conduct the end-to-end tests specified in the verification checklist using real audio, from AudioCapture through to the OverlayView colour. | Whole team |
| Before final submission | Review the requirement sign-off section in the verification checklist and confirm that all 21 requirements have passed their specified verification procedures. | PM and component owners |

Justification: The tests that can be automated (known frequency, expected colour output, error paths) run on every change because they are inexpensive and catch regressions early. The two that need a human (audio comparison, visual colour check) run before review so reviewers can examine the evidence. AppModel is inspected immediately because every other component depends on it, and a design flaw there becomes more expensive to fix as development progresses. Keeping the detailed procedures and acceptance criteria in the verification checklist also allows us to track results consistently without duplicating information in the main project plan. The verification plan explains why each method was chosen, while the checklist provides the steps and criteria used to determine whether the requirements have been met.

### How resilient is our plan?

| Crisis | How the plan responds |
| --- | --- |
| Illness or injury (a member is out for several days) | Every component has a backup owner who also reviews its pull requests, so they already know the code. The PM reassigns the task the same day. Tasks on the board include acceptance criteria, so someone else can pick them up without a handover. The 23rd–26th window absorbs a slip. |
| PM is unavailable | Kevin takes over the board and meeting agenda. The agenda format is fixed (progress, problems, test results, next week), so it is easy to run. |
| API limitation (AudioCapture cannot capture the default output device on someone's OS, or needs special permissions) | AudioCapture is due first (18th), so the problem shows up early. Fallback: capture through a loopback or virtual audio device, or read audio from a file, so the other modules are not blocked. The AudioCapture interface stays narrow so the audio source can be swapped without touching other components. |
| Difficult-to-fix bug (FFT accuracy, colour mapping) | Time-box: if someone is stuck for more than a day, they post in Discord and a second person pairs with them. Our tests start small (1–2 frequencies, black and white maps), so the bug is isolated early. FrequencyAnalyser can fall back to an existing FFT library if the custom one fails. |
| A late module blocks the others | FrequencyAnalyser and ColorMapper are tested with synthetic inputs (a known-frequency audio file, a hand-made frequency map), so they do not wait on AudioCapture or AppModel. |
| Merge conflicts or integration failures | Separate branches per component, reviewed pull requests, and a dedicated integration window before the 27th. |

Worked scenario: If Taj is sick on the 20th, ColorMapper (due 22nd) slips. The PM asks Kevin (its backup) to take it over, and since ColorMapper only needs synthetic test inputs, it can still be done by about the 24th, inside the integration window and before the 27th deadline.

Trigger rule: If a task is not In Review by its deadline, the PM checks in that day and decides whether to reassign it.
Approach
