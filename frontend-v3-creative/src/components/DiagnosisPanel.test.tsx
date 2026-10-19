/**
 * Tests for DiagnosisPanel — main diagnostic surface that renders
 * differential diagnosis rows, CDSS scores, and the safety badge.
 *
 * Covers:
 *   - empty differential renders without crashing
 *   - differential rows are sorted by confidence (desc), highest first
 *   - safety badge derives from critic_review.safety_flag (red→urgent etc.)
 *   - explicit safety_level on the result wins over critic_review (forward-compat)
 *   - CDSS score cards render with the correct risk-level label
 *   - clicking a diagnosis row reveals supporting / against evidence
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import DiagnosisPanel from './DiagnosisPanel';
import type { DiagnosisResult } from '@/types/medichain';

function makeResult(overrides: Partial<DiagnosisResult> = {}): DiagnosisResult {
  return {
    differential_diagnosis: [],
    recommended_tests: [],
    reasoning_chain: '',
    ...overrides,
  };
}

describe('DiagnosisPanel', () => {
  it('renders without crashing on an empty differential', () => {
    const { container } = render(<DiagnosisPanel result={makeResult()} />);
    // Component mounts and surfaces the empty-state message instead of crashing.
    expect(container.querySelector('div')).toBeTruthy();
    expect(screen.getByText(/No diagnoses generated/i)).toBeTruthy();
  });

  it('renders diagnosis entries sorted by confidence (highest first)', () => {
    const result = makeResult({
      differential_diagnosis: [
        { diagnosis: 'Migraine', confidence: 35, supporting_evidence: [], against_evidence: [], source: 'rag' },
        { diagnosis: 'Acute meningitis', confidence: 88, supporting_evidence: [], against_evidence: [], source: 'rag' },
        { diagnosis: 'Tension headache', confidence: 62, supporting_evidence: [], against_evidence: [], source: 'rag' },
      ],
    });

    render(<DiagnosisPanel result={result} />);
    const rendered = screen.getAllByRole('button').map((btn) => btn.textContent || '');
    const meningitisIdx = rendered.findIndex((t) => t.includes('Acute meningitis'));
    const tensionIdx = rendered.findIndex((t) => t.includes('Tension headache'));
    const migraineIdx = rendered.findIndex((t) => t.includes('Migraine'));
    // All three are rendered, and meningitis (88) appears before tension (62) before migraine (35).
    expect(meningitisIdx).toBeGreaterThanOrEqual(0);
    expect(meningitisIdx).toBeLessThan(tensionIdx);
    expect(tensionIdx).toBeLessThan(migraineIdx);
  });

  it('maps critic_review.safety_flag=red → "Urgent" badge', () => {
    const result = makeResult({
      critic_review: {
        approval: false,
        safety_flag: 'red',
        issues: [],
        final_assessment: 'High suspicion of meningitis — admit now.',
      },
    });
    render(<DiagnosisPanel result={result} />);
    expect(screen.getByText(/urgent/i)).toBeTruthy();
  });

  it('explicit safety_level overrides critic_review.safety_flag', () => {
    const result = makeResult({
      safety_level: 'caution',
      critic_review: {
        approval: false,
        safety_flag: 'red',
        issues: [],
        final_assessment: '',
      },
    });
    render(<DiagnosisPanel result={result} />);
    // Forward-compat path wins: explicit safety_level=caution beats safety_flag=red.
    expect(screen.getByText(/caution/i)).toBeTruthy();
    expect(screen.queryByText(/urgent/i)).toBeFalsy();
  });

  it('renders CDSS score cards with the correct risk badge', () => {
    const result = makeResult({
      cdss_scores: [
        { tool_name: 'Wells (PE)', score: 6, max_score: 12.5, risk_level: 'high', recommendation: 'Consider CTPA.' },
        { tool_name: 'CURB-65', score: 1, max_score: 5, risk_level: 'low', recommendation: 'Outpatient.' },
      ],
    });
    render(<DiagnosisPanel result={result} />);
    expect(screen.getByText('Wells (PE)')).toBeTruthy();
    expect(screen.getByText('HIGH')).toBeTruthy();
    expect(screen.getByText('CURB-65')).toBeTruthy();
    expect(screen.getByText('LOW')).toBeTruthy();
  });

  it('clicking a diagnosis row toggles supporting / against evidence', () => {
    const result = makeResult({
      differential_diagnosis: [
        {
          diagnosis: 'Acute meningitis',
          confidence: 88,
          supporting_evidence: ['fever', 'neck stiffness'],
          against_evidence: ['no photophobia'],
          source: 'rag',
        },
      ],
    });
    render(<DiagnosisPanel result={result} />);

    // Evidence is hidden by default
    expect(screen.queryByText('fever')).toBeFalsy();

    const row = screen.getByRole('button', { name: /Acute meningitis/i });
    fireEvent.click(row);

    expect(screen.getByText('fever')).toBeTruthy();
    expect(screen.getByText('neck stiffness')).toBeTruthy();
    expect(screen.getByText('no photophobia')).toBeTruthy();
  });
});
