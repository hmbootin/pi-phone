import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SettingsPage } from '../pages/SettingsPage';
import { db } from '../mocks/handlers';
import { renderPage } from './utils';

describe('SettingsPage', () => {
  it('loads settings, edits several fields, and saves them', async () => {
    const { user } = renderPage(<SettingsPage />);
    const max = await screen.findByLabelText('Max minutes per call');
    expect(max).toHaveValue(10);

    await user.clear(max);
    await user.type(max, '15');
    await user.selectOptions(screen.getByLabelText('Unknown callers'), 'voicemail');
    const start = screen.getByLabelText('Start');
    await user.clear(start);
    await user.type(start, '20:00');
    await user.type(screen.getByLabelText('Email'), 'parent@example.com');

    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    expect(await screen.findByText('Settings saved.')).toBeInTheDocument();

    expect(db.settings.max_call_minutes).toBe(15);
    expect(db.settings.unknown_caller_policy).toBe('voicemail');
    expect(db.settings.quiet_hours).toEqual({ start: '20:00', end: '07:30', tz: 'America/Chicago' });
    expect(db.settings.notifications).toEqual({ ntfy_topic: 'tincan-home', email: 'parent@example.com' });
  });

  it('starts a test call for a chosen contact', async () => {
    const { user } = renderPage(<SettingsPage />);
    await screen.findByLabelText('Max minutes per call');
    const btn = screen.getByRole('button', { name: 'Test call' });
    expect(btn).toBeDisabled();
    await user.selectOptions(screen.getByLabelText('Contact to use'), 'Grandma');
    await user.click(btn);
    expect(await screen.findByText(/Test call started/)).toBeInTheDocument();
  });
});
