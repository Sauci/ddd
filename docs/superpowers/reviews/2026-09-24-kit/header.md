# Complete review of DDD, 2026-09-24

A full review of the whole project after release 0.11.0, run as a sequence of independent passes,
each by one reviewer reading the material fresh, followed by a verification of every finding by a
second reviewer and two sweeps for what the passes missed. It follows the review of 2026-09-15
(branch `review/complete-review-2026-09-15`), whose findings were fixed on 2026-09-16; each pass
records the status of that review's findings in its area. What it finds is to be fixed in 0.11.1.

Since 2026-09-15 the project gained the local web GUI (`ddd gui`, milestones 1 to 7 of its plan),
record layouts with point counts, dictionary format 9 and release 0.11.0: 393 commits on master.
The GUI is reviewed in two passes of its own, server side (7) and front end (8).

Line numbers refer to master at `faee81e` unless a pass says otherwise. Work in progress: passes are
added as they finish, and the summary is written last.
