import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ContactsPage } from '../pages/ContactsPage';
import { db } from '../mocks/handlers';
import { renderPage } from './utils';

describe('Do-not-disturb quick actions', () => {
  it('sets DND for 1h and clears it', async () => {
    const { user } = renderPage(<ContactsPage />);
    const grandma = await screen.findByRole('article', { name: 'Grandma' });
    expect(grandma).not.toHaveTextContent(/Do not disturb ·/);

    await user.click(within(grandma).getByRole('button', { name: '1h' }));
    await waitFor(() => expect(grandma).toHaveTextContent(/Do not disturb · until/));
    const until = db.contacts.find((c) => c.name === 'Grandma')!.dnd_until!;
    const delta = new Date(until).getTime() - Date.now();
    expect(delta).toBeGreaterThan(55 * 60_000);
    expect(delta).toBeLessThanOrEqual(60 * 60_000);

    await user.click(within(grandma).getByRole('button', { name: 'Clear' }));
    await waitFor(() => expect(grandma).not.toHaveTextContent(/Do not disturb ·/));
    expect(db.contacts.find((c) => c.name === 'Grandma')!.dnd_until).toBeNull();
  });

  it('"until tomorrow 7:30" sends an absolute timestamp at 07:30 local', async () => {
    const { user } = renderPage(<ContactsPage />);
    const grandpa = await screen.findByRole('article', { name: 'Grandpa' });
    await user.click(within(grandpa).getByRole('button', { name: 'Until tomorrow 7:30' }));
    await waitFor(() => expect(db.contacts.find((c) => c.name === 'Grandpa')!.dnd_until).not.toBeNull());
    const d = new Date(db.contacts.find((c) => c.name === 'Grandpa')!.dnd_until!);
    expect(d.getHours()).toBe(7);
    expect(d.getMinutes()).toBe(30);
    expect(d.getTime()).toBeGreaterThan(Date.now());
    expect(grandpa).toHaveTextContent(/7:30/);
  });
});
