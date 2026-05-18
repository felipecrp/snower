import { Decision, ReviewSet } from '../models';

import { buildGroups, buildIterationSummaries, buildOverviewSummary, buildSetSummaries } from './results';

function work(
  bib_key: string,
  title: string,
  year?: number | null,
  venue?: string | null,
) {
  return {
    bib_key,
    title,
    authors: ['Doe, Jane'],
    year,
    venue,
  };
}

function decision(
  bib_id: string,
  verdict: 'accept' | 'reject',
  researcher_id: string,
): Decision {
  return {
    bib_id,
    verdict,
    researcher_id,
    decided_at: '2026-05-17T00:00:00Z',
  };
}

describe('results aggregation', () => {
  const sets: ReviewSet[] = [
    {
      id: '00-start',
      kind: 'start',
      iteration: 0,
      works: [
        work('start-a', 'Accepted in start', 2020, 'ICSE'),
        work('start-b', 'Rejected in start', 2021, null),
        work('start-c', 'Undecided in start', null, 'TSE'),
      ],
    },
    {
      id: '01-backward',
      kind: 'backward',
      iteration: 1,
      works: [
        work('bwd-a', 'Accepted backward', 2022, 'ESEM'),
        work('bwd-b', 'Rejected backward', 2022, 'ESEM'),
      ],
    },
    {
      id: 'orphan',
      kind: 'orphan',
      iteration: 0,
      works: [
        work('orph-a', 'Accepted orphan', 2024, 'SANER'),
      ],
    },
  ];

  const allDecisions: Record<string, Decision[]> = {
    '00-start': [
      decision('start-a', 'accept', 'a'),
      decision('start-a', 'accept', 'b'),
      decision('start-b', 'reject', 'a'),
      decision('start-b', 'reject', 'b'),
      decision('start-c', 'accept', 'a'),
      decision('start-c', 'reject', 'b'),
    ],
    '01-backward': [
      decision('bwd-a', 'accept', 'a'),
      decision('bwd-a', 'reject', 'b'),
      decision('bwd-a', 'accept', 'c'),
      decision('bwd-b', 'reject', 'a'),
    ],
    orphan: [
      decision('orph-a', 'accept', 'a'),
    ],
  };

  it('builds per-set consensus summaries and excludes orphan from the main flow', () => {
    const summaries = buildSetSummaries(sets, allDecisions);

    expect(summaries.map((summary) => summary.set.id)).toEqual(['00-start', '01-backward']);
    expect(summaries[0]).toMatchObject({
      total: 3,
      accepted: 1,
      rejected: 1,
      unresolved: 1,
      acceptanceRate: 33,
    });
    expect(summaries[1]).toMatchObject({
      total: 2,
      accepted: 1,
      rejected: 1,
      unresolved: 0,
      acceptanceRate: 50,
    });
  });

  it('builds the overview totals across regular sets only', () => {
    const overview = buildOverviewSummary(buildSetSummaries(sets, allDecisions));

    expect(overview).toEqual({
      total: 5,
      accepted: 2,
      rejected: 2,
      unresolved: 1,
      acceptanceRate: 40,
    });
  });

  it('aggregates step summaries by iteration and keeps set sections inside each iteration', () => {
    const iterations = buildIterationSummaries(buildSetSummaries(sets, allDecisions));

    expect(iterations).toHaveLength(2);
    expect(iterations[0]).toMatchObject({
      iteration: 0,
      total: 3,
      accepted: 1,
      rejected: 1,
      unresolved: 1,
    });
    expect(iterations[0].sections.map((section) => section.set.id)).toEqual(['00-start']);
    expect(iterations[1].sections.map((section) => section.set.id)).toEqual(['01-backward']);
  });

  it('groups accepted papers by venue with an unknown bucket', () => {
    const summaries = buildSetSummaries(sets, allDecisions);
    const groups = buildGroups(
      summaries.flatMap((summary) => summary.acceptedPapers),
      (paper) => paper.work.venue?.trim() || 'Unknown venue',
    );

    expect(groups.map((group) => group.label)).toEqual(['ESEM', 'ICSE']);
    expect(groups[0].papers[0].work.title).toBe('Accepted backward');
  });

  it('groups accepted papers by year with an unknown bucket', () => {
    const summaries = buildSetSummaries(sets, allDecisions);
    const groups = buildGroups(
      [
        ...summaries.flatMap((summary) => summary.acceptedPapers),
        {
          work: work('extra', 'Accepted unknown year', null, 'TOSEM'),
          setId: '02-forward',
          setKind: 'forward',
          iteration: 2,
        },
      ],
      (paper) => paper.work.year?.toString() || 'Unknown year',
    );

    expect(groups.map((group) => group.label)).toEqual(['2020', '2022', 'Unknown year']);
  });
});
