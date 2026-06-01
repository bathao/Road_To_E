// Valid final scores for each best-of format, split into wins and losses.
// Used to render the score picker as tap-buttons (no typing).

export interface Score {
  my: number;
  opp: number;
}

export function setsToWin(bestOf: number): number {
  return Math.floor(bestOf / 2) + 1; // BO3->2, BO5->3, BO7->4
}

export function validScores(bestOf: number): { wins: Score[]; losses: Score[] } {
  const need = setsToWin(bestOf);
  const wins: Score[] = [];
  const losses: Score[] = [];
  for (let opp = 0; opp < need; opp++) {
    wins.push({ my: need, opp });
    losses.push({ my: opp, opp: need });
  }
  return { wins, losses };
}
