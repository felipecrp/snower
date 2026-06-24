# Snower

Snower is a tool to assist the snowballing process in a Systematic Literature Review (SLR). The snowballing workflow starts from a seed set of papers and expands it via backward (references) and forward (citations) snowballing, with screening decisions across iterations.

A paper's `references` and `citations` edges drive **automatic round placement**: instead of assigning papers to sets by hand, you declare the seeds and the citation edges, and Snower derives each paper's set (a backward/forward direction and a round number) by snowballing from the seeds. Screening is done by **excluding** a paper, which retracts its contribution and re-derives everyone downstream. See [doc/snowballing.md](doc/snowballing.md), [doc/project.md](doc/project.md), and [doc/persistence.md](doc/persistence.md).
