import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { HomePage } from '../pages/HomePage';
import { db, startSimulatedCall } from '../mocks/handlers';
import { renderPage } from './utils';

describe('HomePage', () => {
  it('shows line status, counts, and backup info', async () => {
    renderPage(<HomePage />);
    expect(await screen.findByTitle('Asterisk: connected')).toBeInTheDocument();
    expect(screen.getByTitle('Phone: registered')).toBeInTheDocument();
    expect(screen.getByTitle('Trunk: registered')).toBeInTheDocument();
    const unlistened = db.recordings.filter((r) => !r.listened).length;
    expect(await screen.findByRole('link', { name: new RegExp(`^${unlistened} memor`) })).toBeInTheDocument();
    expect(screen.getByText('Waiting to upload')).toBeInTheDocument();
  });

  it('shows the active call and can hang up', async () => {
    startSimulatedCall(1, 'inbound');
    const { user } = renderPage(<HomePage />);
    const card = await screen.findByRole('region', { name: 'Active call' });
    expect(card).toHaveTextContent('Grandma called');
    await user.click(screen.getByRole('button', { name: 'Hang up' }));
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Active call' })).not.toBeInTheDocument());
    expect(db.activeCallId).toBeNull();
    expect(db.calls[0]!.outcome).toBe('completed');
  });
});
